"""Voyage embedding transport tests (G-E).

Wire-level behavior against ``httpx.MockTransport`` — no network anywhere.
The transport must batch deterministically, re-order vectors by the
provider's ``index`` field, map failures onto the retryable/permanent
``TransportError`` taxonomy, and never leak request/response bodies into
error messages.
"""

from __future__ import annotations

import json

import httpx
import pytest

from agentic_calendar.contracts.reason_codes import ReasonCode
from agentic_calendar.llm_nodes.anthropic_adapter import TransportError
from agentic_calendar.llm_nodes.voyage_embeddings import (
    EmbeddingBatch,
    EmbeddingConfig,
    EmbeddingTransport,
    VoyageEmbeddingsTransport,
)

CONFIG = EmbeddingConfig()


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def _ok_payload(count: int, *, dimension: int = 4, tokens: int = 7) -> dict:
    return {
        "object": "list",
        "data": [
            {"object": "embedding", "index": i, "embedding": [float(i)] * dimension}
            for i in range(count)
        ],
        "usage": {"total_tokens": tokens},
    }


def test_satisfies_transport_protocol() -> None:
    transport = VoyageEmbeddingsTransport(api_key="k", http_client=_client(lambda r: None))
    assert isinstance(transport, EmbeddingTransport)


def test_missing_api_key_is_typed_auth_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VOYAGE_API_KEY", raising=False)
    with pytest.raises(TransportError) as excinfo:
        VoyageEmbeddingsTransport()
    assert excinfo.value.retryable is False
    assert excinfo.value.reason_code is ReasonCode.LLM_AUTH_FAILED


def test_request_shape_and_auth_header() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=_ok_payload(2))

    transport = VoyageEmbeddingsTransport(api_key="key-123", http_client=_client(handler))
    result = transport.embed(["alpha", "beta"], input_type="query", config=CONFIG)

    assert len(seen) == 1
    request = seen[0]
    assert request.url == "https://api.voyageai.com/v1/embeddings"
    assert request.headers["authorization"] == "Bearer key-123"
    body = json.loads(request.content)
    assert body == {
        "model": "voyage-3.5",
        "input": ["alpha", "beta"],
        "input_type": "query",
        "output_dimension": 1024,
    }
    assert isinstance(result, EmbeddingBatch)
    assert result.total_tokens == 7


def test_vectors_reordered_by_provider_index() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": 1, "embedding": [1.0, 1.0]},
                    {"index": 0, "embedding": [0.0, 0.0]},
                ],
                "usage": {"total_tokens": 3},
            },
        )

    transport = VoyageEmbeddingsTransport(api_key="k", http_client=_client(handler))
    result = transport.embed(["first", "second"], input_type="document", config=CONFIG)
    assert result.vectors == [[0.0, 0.0], [1.0, 1.0]]


def test_batching_splits_requests_and_sums_usage() -> None:
    batch_sizes: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        count = len(json.loads(request.content)["input"])
        batch_sizes.append(count)
        return httpx.Response(200, json=_ok_payload(count, tokens=count * 10))

    config = EmbeddingConfig(batch_size=2)
    transport = VoyageEmbeddingsTransport(api_key="k", http_client=_client(handler))
    result = transport.embed(
        ["a", "b", "c", "d", "e"], input_type="document", config=config
    )
    assert batch_sizes == [2, 2, 1]
    assert len(result.vectors) == 5
    assert result.total_tokens == 20 + 20 + 10


def test_empty_input_makes_no_call() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("no HTTP call expected for empty input")

    transport = VoyageEmbeddingsTransport(api_key="k", http_client=_client(handler))
    result = transport.embed([], input_type="document", config=CONFIG)
    assert result == EmbeddingBatch(vectors=[], total_tokens=0, latency_ms=0)


@pytest.mark.parametrize(
    ("status", "retryable", "reason_code"),
    [
        (401, False, ReasonCode.LLM_AUTH_FAILED),
        (403, False, ReasonCode.LLM_AUTH_FAILED),
        (429, True, ReasonCode.LLM_RATE_LIMITED),
        (400, False, ReasonCode.LLM_CALL_FAILED),
        (422, False, ReasonCode.LLM_CALL_FAILED),
        (500, True, ReasonCode.LLM_CALL_FAILED),
        (529, True, ReasonCode.LLM_CALL_FAILED),
    ],
)
def test_http_status_maps_to_error_taxonomy(
    status: int, retryable: bool, reason_code: ReasonCode
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json={"detail": "SECRET-BODY"})

    config = EmbeddingConfig(max_transport_retries=0)
    transport = VoyageEmbeddingsTransport(api_key="k", http_client=_client(handler))
    with pytest.raises(TransportError) as excinfo:
        transport.embed(["x"], input_type="document", config=config)
    assert excinfo.value.retryable is retryable
    assert excinfo.value.reason_code is reason_code
    # Bodies contain corpus text in real runs — they must never leak.
    assert "SECRET-BODY" not in str(excinfo.value)


def test_timeout_is_retried_with_exponential_backoff_then_raised() -> None:
    calls: list[int] = []
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        raise httpx.ConnectTimeout("boom")

    config = EmbeddingConfig(max_transport_retries=2, backoff_base_seconds=4.0)
    transport = VoyageEmbeddingsTransport(
        api_key="k", http_client=_client(handler), sleeper=sleeps.append
    )
    with pytest.raises(TransportError) as excinfo:
        transport.embed(["x"], input_type="document", config=config)
    assert excinfo.value.retryable is True
    assert len(calls) == 3  # initial + 2 bounded retries
    assert sleeps == [4.0, 8.0]  # deterministic exponential backoff


def test_retryable_failure_then_success_recovers_after_one_backoff() -> None:
    calls: list[int] = []
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        if len(calls) == 1:
            return httpx.Response(429, json={})
        return httpx.Response(200, json=_ok_payload(1))

    config = EmbeddingConfig(max_transport_retries=1, backoff_base_seconds=2.0)
    transport = VoyageEmbeddingsTransport(
        api_key="k", http_client=_client(handler), sleeper=sleeps.append
    )
    result = transport.embed(["x"], input_type="document", config=config)
    assert len(calls) == 2
    assert sleeps == [2.0]
    assert len(result.vectors) == 1


def test_success_path_never_sleeps() -> None:
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_ok_payload(1))

    transport = VoyageEmbeddingsTransport(
        api_key="k", http_client=_client(handler), sleeper=sleeps.append
    )
    transport.embed(["x"], input_type="document", config=CONFIG)
    assert sleeps == []


def test_permanent_failure_is_not_retried() -> None:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(400, json={})

    config = EmbeddingConfig(max_transport_retries=2)
    transport = VoyageEmbeddingsTransport(api_key="k", http_client=_client(handler))
    with pytest.raises(TransportError):
        transport.embed(["x"], input_type="document", config=config)
    assert len(calls) == 1


@pytest.mark.parametrize(
    "payload",
    [
        {"data": [{"index": 0, "embedding": [1.0]}], "usage": {}},  # count mismatch
        {"data": [{"index": 5, "embedding": [1.0]}, {"index": 0, "embedding": [1.0]}]},
        {"data": "not-a-list"},
        {"data": [{"index": 0}, {"index": 1, "embedding": [1.0]}]},
    ],
)
def test_malformed_response_is_typed_permanent_error(payload: dict) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    config = EmbeddingConfig(max_transport_retries=0)
    transport = VoyageEmbeddingsTransport(api_key="k", http_client=_client(handler))
    with pytest.raises(TransportError) as excinfo:
        transport.embed(["a", "b"], input_type="document", config=config)
    assert excinfo.value.retryable is False


def test_cost_estimate_matches_axiom_09_arithmetic() -> None:
    config = EmbeddingConfig()  # $0.06 per 1M tokens
    assert config.estimate_cost_usd(0) == 0.0
    assert config.estimate_cost_usd(1_000_000) == pytest.approx(0.06)
    # The measured pinned-snapshot corpus (~220k tokens) costs about a cent.
    assert config.estimate_cost_usd(220_000) == pytest.approx(0.0132)
