"""Voyage AI embedding transport (grounding-RAG G-E — gated, user-approved).

Anthropic has no embeddings endpoint, so dense retrieval means a second
model provider. This transport is that integration, and it follows the
eval-judge precedent exactly (see ``eval_judge.py``): it is **not** one of
the four LLM workflow node classes (axiom 01), it never routes through
``_GenerationEngine`` (no contract/repair semantics apply to a vector), and
it stays deliberately outside the node-keyed ``LlmCallLog`` taxonomy. Its
observability is the calling tool's job: the embed CLI enforces a hard token
cap and reports measured tokens / cost / latency per run.

Embeddings never touch runtime routing: vectors are plain data the
``retrieval/`` region consumes through its vector cache — this module is
composed only from ``tools/`` (offline, ask-first, per the operating
contract's networked-command gate).

The HTTP client is ``httpx``, imported lazily like the Anthropic SDK is in
``anthropic_adapter.py``. httpx is a hard runtime dependency of the
``anthropic`` package, so it is always importable here without adding a
dependency of our own. The API key comes from ``VOYAGE_API_KEY`` in the
environment, never code. Error messages carry status codes and exception
type names only — never request or response bodies (they contain corpus
text and would leak into logs).
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from agentic_calendar.contracts.reason_codes import ReasonCode

from .anthropic_adapter import TransportError

_VOYAGE_EMBEDDINGS_URL = "https://api.voyageai.com/v1/embeddings"

#: Voyage caps batches at 1000 inputs; we stay far below it so a single
#: oversized request can never blow the per-request token limit.
_MAX_BATCH_SIZE = 128

#: What a text is embedded *as*. Voyage prepends a retrieval-specific prompt
#: per type, so the same text embeds to different vectors under each — the
#: vector cache keys on this too.
EmbeddingInputType = Literal["document", "query"]


class EmbeddingConfig(BaseModel):
    """Pinned embedding model + pricing (axiom 09 disclosure applies).

    ``voyage-3.5`` at $0.06 per 1M tokens is the user-approved G-E decision
    (2026-07-06); the price is a pricing-table constant pending measurement,
    like every figure in axiom 09.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    model_name: str = "voyage-3.5"
    price_per_mtok: float = Field(default=0.06, ge=0.0)
    output_dimension: int = Field(default=1024, ge=1)
    batch_size: int = Field(default=_MAX_BATCH_SIZE, ge=1, le=_MAX_BATCH_SIZE)
    timeout_seconds: float = Field(default=60.0, gt=0.0)
    max_transport_retries: int = Field(default=4, ge=0)
    backoff_base_seconds: float = Field(default=4.0, ge=0.0)
    """Retry ``n`` (0-based) sleeps ``backoff_base_seconds * 2**n`` before
    re-posting a retryable failure — deterministic exponential backoff. The
    default survives a per-minute rate-limit window (4+8+16+32 = 60s across
    the four default retries), which is what free-tier provider accounts
    enforce."""

    def estimate_cost_usd(self, total_tokens: int) -> float:
        return (total_tokens / 1_000_000) * self.price_per_mtok


class EmbeddingBatch(BaseModel):
    """One provider call's result: vectors in input order + usage."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    vectors: list[list[float]]
    total_tokens: int = Field(ge=0)
    latency_ms: int = Field(ge=0)


@runtime_checkable
class EmbeddingTransport(Protocol):
    """Single-call embedding surface. Tests inject a deterministic fake."""

    def embed(
        self,
        texts: list[str],
        *,
        input_type: EmbeddingInputType,
        config: EmbeddingConfig,
    ) -> EmbeddingBatch: ...


class VoyageEmbeddingsTransport:
    """Real Voyage AI transport over httpx.

    One ``embed`` call issues one POST per ``config.batch_size`` slice and
    concatenates the results in input order (the provider tags each vector
    with its input index; we re-order by it rather than trusting response
    order). Retries are bounded and apply only to retryable failures.
    """

    def __init__(
        self,
        api_key: str | None = None,
        http_client: Any | None = None,
        *,
        sleeper: Callable[[float], None] | None = None,
    ) -> None:
        key = api_key if api_key is not None else os.environ.get("VOYAGE_API_KEY")
        if not key:
            raise TransportError(
                "VOYAGE_API_KEY is not set; the Voyage embedding transport "
                "requires it in the environment",
                retryable=False,
                reason_code=ReasonCode.LLM_AUTH_FAILED,
            )
        self._api_key = key
        if http_client is None:
            import httpx

            http_client = httpx.Client()
        self._client = http_client
        self._sleep = sleeper if sleeper is not None else time.sleep

    def embed(
        self,
        texts: list[str],
        *,
        input_type: EmbeddingInputType,
        config: EmbeddingConfig,
    ) -> EmbeddingBatch:
        if not texts:
            return EmbeddingBatch(vectors=[], total_tokens=0, latency_ms=0)
        vectors: list[list[float]] = []
        total_tokens = 0
        started = time.monotonic()
        for offset in range(0, len(texts), config.batch_size):
            batch = texts[offset : offset + config.batch_size]
            payload = self._post_with_bounded_retries(batch, input_type, config)
            vectors.extend(_vectors_in_input_order(payload, expected=len(batch)))
            total_tokens += _usage_tokens(payload)
        latency_ms = int((time.monotonic() - started) * 1000)
        return EmbeddingBatch(
            vectors=vectors, total_tokens=total_tokens, latency_ms=latency_ms
        )

    def _post_with_bounded_retries(
        self,
        batch: list[str],
        input_type: EmbeddingInputType,
        config: EmbeddingConfig,
    ) -> dict[str, Any]:
        last_error: TransportError | None = None
        for attempt in range(config.max_transport_retries + 1):
            if attempt > 0:
                # Deterministic exponential backoff before every re-post —
                # rate-limit windows are per-minute; hammering them is both
                # impolite and useless.
                self._sleep(config.backoff_base_seconds * 2 ** (attempt - 1))
            try:
                return self._post_once(batch, input_type, config)
            except TransportError as exc:
                if not exc.retryable:
                    raise
                last_error = exc
        assert last_error is not None
        raise last_error

    def _post_once(
        self,
        batch: list[str],
        input_type: EmbeddingInputType,
        config: EmbeddingConfig,
    ) -> dict[str, Any]:
        import httpx

        try:
            response = self._client.post(
                _VOYAGE_EMBEDDINGS_URL,
                json={
                    "model": config.model_name,
                    "input": batch,
                    "input_type": input_type,
                    "output_dimension": config.output_dimension,
                },
                headers={"Authorization": f"Bearer {self._api_key}"},
                timeout=config.timeout_seconds,
            )
        except httpx.HTTPError as exc:
            # Connection failures and timeouts: transient provider weather.
            raise TransportError(
                f"embedding call failed before a response: {type(exc).__name__}",
                retryable=True,
                reason_code=ReasonCode.LLM_CALL_FAILED,
            ) from exc
        if response.status_code in (401, 403):
            raise TransportError(
                f"embedding provider rejected credentials: HTTP {response.status_code}",
                retryable=False,
                reason_code=ReasonCode.LLM_AUTH_FAILED,
            )
        if response.status_code == 429:
            raise TransportError(
                "embedding provider rate limited: HTTP 429",
                retryable=True,
                reason_code=ReasonCode.LLM_RATE_LIMITED,
            )
        if 400 <= response.status_code < 500:
            raise TransportError(
                f"embedding provider rejected the request: HTTP {response.status_code}",
                retryable=False,
                reason_code=ReasonCode.LLM_CALL_FAILED,
            )
        if response.status_code >= 500:
            raise TransportError(
                f"embedding provider call failed: HTTP {response.status_code}",
                retryable=True,
                reason_code=ReasonCode.LLM_CALL_FAILED,
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise TransportError(
                "embedding provider returned unparseable JSON",
                retryable=True,
                reason_code=ReasonCode.LLM_CALL_FAILED,
            ) from exc
        if not isinstance(payload, dict):
            raise TransportError(
                "embedding provider returned a non-object payload",
                retryable=False,
                reason_code=ReasonCode.LLM_CALL_FAILED,
            )
        return payload


def _vectors_in_input_order(payload: dict[str, Any], *, expected: int) -> list[list[float]]:
    """Extract vectors ordered by the provider's per-item ``index`` field.

    A count or index mismatch is a malformed response — typed raise, never a
    silently misaligned cache write (a vector cached against the wrong text
    would corrupt every downstream ranking).
    """
    data = payload.get("data")
    if not isinstance(data, list) or len(data) != expected:
        raise TransportError(
            f"embedding response has {len(data) if isinstance(data, list) else 'no'}"
            f" items where {expected} were requested",
            retryable=False,
            reason_code=ReasonCode.LLM_CALL_FAILED,
        )
    by_index: dict[int, list[float]] = {}
    for item in data:
        if not isinstance(item, dict):
            raise TransportError(
                "embedding response item is not an object",
                retryable=False,
                reason_code=ReasonCode.LLM_CALL_FAILED,
            )
        index = item.get("index")
        embedding = item.get("embedding")
        if not isinstance(index, int) or not isinstance(embedding, list):
            raise TransportError(
                "embedding response item lacks an integer index or an "
                "embedding list",
                retryable=False,
                reason_code=ReasonCode.LLM_CALL_FAILED,
            )
        by_index[index] = [float(value) for value in embedding]
    if sorted(by_index) != list(range(expected)):
        raise TransportError(
            "embedding response indices do not cover the request exactly",
            retryable=False,
            reason_code=ReasonCode.LLM_CALL_FAILED,
        )
    return [by_index[i] for i in range(expected)]


def _usage_tokens(payload: dict[str, Any]) -> int:
    usage = payload.get("usage")
    if isinstance(usage, dict):
        tokens = usage.get("total_tokens")
        if isinstance(tokens, int) and tokens >= 0:
            return tokens
    return 0
