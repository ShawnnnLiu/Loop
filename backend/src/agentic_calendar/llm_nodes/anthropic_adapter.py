"""Real Anthropic adapters for the four allowed nodes (Phase 8c).

LLMs propose; deterministic infrastructure disposes. These adapters keep that
boundary intact while swapping the fixture fakes for real SDK calls:

- **Schema-enforced generation**: requests use the SDK's structured-output
  path shaped by the target contract — and the parsed result is **still
  re-validated** with ``model_validate`` before it leaves the boundary
  (axiom 22: never trust the enforcement).
- **Deterministic limits**: plain Python code owns the retry caps — at most
  ``max_sdk_retries`` transport retries per attempt and at most
  ``max_repair_attempts`` contract-repair re-prompts (axiom 04's bound).
  Exhaustion raises :class:`LLMGenerationError` carrying a typed
  ``reason_code``; the caller routes ``error_requires_user``. No silent
  failure, no fabricated output, and nothing here can reach a calendar
  write (ADR-0006).
- **Observability**: every provider API call appends exactly one
  :class:`~agentic_calendar.llm_nodes.call_log.LlmCallLog` row — counts,
  hashes, and outcome metadata only, never raw prompt/response text. Raw
  content is available solely through an injected ``debug_raw_sink``
  callable (e.g. the smoke CLI's stdout printer) and is never persisted.

The SDK is imported lazily inside :class:`AnthropicMessagesTransport` so the
package stays importable (and fixture nodes stay usable) without it. Model
defaults follow axiom 09's tiering — frontier for the Strategist, mid-tier
for the rest — with pricing from the Claude model table (cached 2026-05-26);
all cost figures are estimates pending measurement (axiom 09 disclosure).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Sequence
from typing import Any, Protocol, cast, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from agentic_calendar.common.clock import Clock
from agentic_calendar.common.errors import AgenticCalendarError
from agentic_calendar.common.ids import IdGenerator
from agentic_calendar.contracts.drift_event import DriftEvent
from agentic_calendar.contracts.reason_codes import ReasonCode
from agentic_calendar.contracts.source_claim import SourceClaim
from agentic_calendar.contracts.strategist_input import StrategistInput
from agentic_calendar.contracts.strategy_constraints import StrategyConstraints
from agentic_calendar.contracts.syllabus_units import SyllabusUnits
from agentic_calendar.contracts.task_plan import TaskPlan
from agentic_calendar.contracts.user_profile import UserProfile
from agentic_calendar.contracts.validation_result import ValidationResult

from .base import LLMNodeError
from .call_log import LlmCallLog, LlmCallLogStore, LlmNodeName, ValidationOutcome
from .reflection_summary import ReflectionSummary, _ensure_no_psychological_labels
from .strategist import _check_against_constraints
from .user_facing_explanation import UserExplanation


class TransportError(AgenticCalendarError):
    """Network, timeout, or provider error — the call produced no response.

    Messages must never contain credentials or raw request content; the real
    transport reports the SDK exception *type*, not its body."""


class TransportResult(BaseModel):
    """Provider-neutral result of one API call."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    payload: dict[str, Any] | None
    """Structured output parsed by the SDK, or None when unparseable."""

    raw_text: str | None
    """Raw response text (hashed for the log; surfaced only via debug sink)."""

    stop_reason: str | None
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    cache_read_tokens: int = Field(default=0, ge=0)


@runtime_checkable
class AnthropicTransport(Protocol):
    """Single-call surface the generation engine depends on.

    Tests inject a fake; production wires :class:`AnthropicMessagesTransport`."""

    def complete(
        self,
        *,
        model_name: str,
        max_tokens: int,
        system: str,
        user_prompt: str,
        output_contract: type[BaseModel],
    ) -> TransportResult: ...


class AnthropicMessagesTransport:
    """Real SDK transport. API key comes from the environment, never code.

    Uses ``client.messages.parse`` so generation is shaped by the contract's
    schema (the SDK strips JSON-Schema constraints the API doesn't support
    and validates them client-side). The engine re-validates regardless."""

    def __init__(self, client: Any | None = None) -> None:
        if client is None:
            import anthropic

            client = anthropic.Anthropic()
        self._client = client

    def complete(
        self,
        *,
        model_name: str,
        max_tokens: int,
        system: str,
        user_prompt: str,
        output_contract: type[BaseModel],
    ) -> TransportResult:
        import anthropic

        try:
            response = self._client.messages.parse(
                model=model_name,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user_prompt}],
                output_format=output_contract,
            )
        except anthropic.APIError as exc:
            # Type name only: SDK exception bodies may quote request content.
            raise TransportError(f"provider call failed: {type(exc).__name__}") from exc

        parsed = getattr(response, "parsed_output", None)
        payload = parsed.model_dump(mode="json") if isinstance(parsed, BaseModel) else None
        # Walk the content blocks untyped: the SDK's block union is broad and
        # we only need the first text body, which we hash rather than store.
        blocks: Sequence[Any] = response.content
        raw_text: str | None = None
        for block in blocks:
            if getattr(block, "type", None) == "text":
                raw_text = str(block.text)
                break
        usage = response.usage
        return TransportResult(
            payload=payload,
            raw_text=raw_text,
            stop_reason=response.stop_reason,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cache_read_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
        )


class AdapterConfig(BaseModel):
    """Per-node generation settings. Caps are deterministic code, not prompts."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    model_name: str = Field(min_length=1)
    prompt_version: str = Field(min_length=1)
    max_tokens: int = Field(gt=0)
    input_price_per_mtok: float = Field(ge=0)
    output_price_per_mtok: float = Field(ge=0)
    max_sdk_retries: int = Field(default=2, ge=0, le=2)
    """Transport retries per attempt (locked smoke safeguard: at most 2)."""
    max_repair_attempts: int = Field(default=2, ge=0, le=2)
    """Contract-repair re-prompts (axiom 04: at most 2)."""

    def estimate_cost_usd(self, *, input_tokens: int, output_tokens: int) -> float:
        """Deterministic estimate from the configured pricing — not a billing fact."""
        return (
            input_tokens * self.input_price_per_mtok
            + output_tokens * self.output_price_per_mtok
        ) / 1_000_000


# Defaults follow axiom 09 model tiering (frontier Strategist, mid-tier rest).
# Prices are $ per 1M tokens from the Claude model table cached 2026-05-26;
# estimates pending production measurement (axiom 09 disclosure). max_tokens
# follows the axiom 09 output budgets (4k/8k strategist/planner); the prose
# nodes get 1024 — the smallest round cap above their ~500/~300 budgets that
# leaves headroom for the structured-output JSON envelope.
STRATEGIST_CONFIG = AdapterConfig(
    model_name="claude-opus-4-8",
    prompt_version="strategist-v1-2026-06-10",
    max_tokens=4096,
    input_price_per_mtok=5.00,
    output_price_per_mtok=25.00,
)
PLANNER_CONFIG = AdapterConfig(
    model_name="claude-haiku-4-5",
    prompt_version="planner-v1-2026-06-10",
    max_tokens=8192,
    input_price_per_mtok=1.00,
    output_price_per_mtok=5.00,
)
REFLECTION_CONFIG = AdapterConfig(
    model_name="claude-haiku-4-5",
    prompt_version="reflection-v1-2026-06-10",
    max_tokens=1024,
    input_price_per_mtok=1.00,
    output_price_per_mtok=5.00,
)
EXPLANATION_CONFIG = AdapterConfig(
    model_name="claude-haiku-4-5",
    prompt_version="explanation-v1-2026-06-10",
    max_tokens=1024,
    input_price_per_mtok=1.00,
    output_price_per_mtok=5.00,
)


class LLMGenerationError(LLMNodeError):
    """Generation failed with a typed ``reason_code``.

    Raised after the deterministic caps are exhausted (or on a refusal); the
    caller routes ``error_requires_user``. Never produces fabricated output."""

    def __init__(self, message: str, *, reason_code: ReasonCode) -> None:
        super().__init__(message)
        self.reason_code = reason_code


#: Raises on a rubric violation (e.g. psych-label scan); treated like a
#: contract rejection and repaired within the bounded loop. Must not raise
#: :class:`LLMGenerationError`.
PostValidator = Callable[[BaseModel], None]


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _canonical_json(model: BaseModel) -> str:
    return json.dumps(model.model_dump(mode="json"), sort_keys=True)


class _GenerationEngine:
    """Shared bounded-generation loop behind all four adapters."""

    def __init__(
        self,
        *,
        node: LlmNodeName,
        contract: type[BaseModel],
        config: AdapterConfig,
        transport: AnthropicTransport,
        store: LlmCallLogStore,
        clock: Clock,
        id_generator: IdGenerator,
        debug_raw_sink: Callable[[str], None] | None = None,
    ) -> None:
        self._node = node
        self._contract = contract
        self._config = config
        self._transport = transport
        self._store = store
        self._clock = clock
        self._ids = id_generator
        self._debug_raw_sink = debug_raw_sink

    def generate(
        self,
        *,
        run_id: str,
        plan_version: str | None,
        system: str,
        user_prompt: str,
        post_validate: PostValidator | None = None,
    ) -> BaseModel:
        repair_context: str | None = None
        for attempt in range(self._config.max_repair_attempts + 1):
            prompt = user_prompt
            if repair_context is not None:
                prompt = (
                    f"{user_prompt}\n\nYour previous output was rejected by "
                    f"deterministic validation. Fix exactly these problems and "
                    f"return the corrected object:\n{repair_context}"
                )
            outcome = self._run_attempt(
                run_id=run_id,
                plan_version=plan_version,
                system=system,
                prompt=prompt,
                attempt=attempt,
                post_validate=post_validate,
            )
            if isinstance(outcome, BaseModel):
                return outcome
            repair_context = outcome
        raise LLMGenerationError(
            f"{self._node.value} output still invalid after "
            f"{self._config.max_repair_attempts} repair attempts",
            reason_code=ReasonCode.REPAIR_LIMIT_EXCEEDED,
        )

    def _run_attempt(
        self,
        *,
        run_id: str,
        plan_version: str | None,
        system: str,
        prompt: str,
        attempt: int,
        post_validate: PostValidator | None,
    ) -> BaseModel | str:
        """One repair attempt: returns the validated model, or the rejection
        text to feed the next repair re-prompt. Terminal failures raise."""
        prompt_hash = _sha256(f"{system}\n{prompt}")
        for sdk_retry in range(self._config.max_sdk_retries + 1):
            is_last_retry = sdk_retry == self._config.max_sdk_retries
            started = self._clock.now()
            try:
                result = self._transport.complete(
                    model_name=self._config.model_name,
                    max_tokens=self._config.max_tokens,
                    system=system,
                    user_prompt=prompt,
                    output_contract=self._contract,
                )
            except TransportError as exc:
                code = (
                    ReasonCode.LLM_RETRY_LIMIT_EXCEEDED
                    if is_last_retry
                    else ReasonCode.LLM_CALL_FAILED
                )
                self._append_row(
                    run_id=run_id,
                    plan_version=plan_version,
                    attempt=attempt,
                    sdk_retry=sdk_retry,
                    result=None,
                    started=started,
                    reason_code=code,
                    truncated=False,
                    refusal=False,
                    prompt_hash=prompt_hash,
                )
                if is_last_retry:
                    raise LLMGenerationError(
                        f"{self._node.value} transport retries exhausted",
                        reason_code=ReasonCode.LLM_RETRY_LIMIT_EXCEEDED,
                    ) from exc
                continue

            if self._debug_raw_sink is not None and result.raw_text is not None:
                self._debug_raw_sink(result.raw_text)

            truncated = result.stop_reason == "max_tokens"
            if result.stop_reason == "refusal":
                self._append_row(
                    run_id=run_id,
                    plan_version=plan_version,
                    attempt=attempt,
                    sdk_retry=sdk_retry,
                    result=result,
                    started=started,
                    reason_code=ReasonCode.LLM_REFUSAL,
                    truncated=truncated,
                    refusal=True,
                    prompt_hash=prompt_hash,
                )
                # A refusal is not transient; retrying the same input is noise.
                raise LLMGenerationError(
                    f"{self._node.value} call refused by the model",
                    reason_code=ReasonCode.LLM_REFUSAL,
                )

            if result.payload is None:
                if truncated:
                    code = (
                        ReasonCode.LLM_RETRY_LIMIT_EXCEEDED
                        if is_last_retry
                        else ReasonCode.LLM_TRUNCATED
                    )
                    self._append_row(
                        run_id=run_id,
                        plan_version=plan_version,
                        attempt=attempt,
                        sdk_retry=sdk_retry,
                        result=result,
                        started=started,
                        reason_code=code,
                        truncated=True,
                        refusal=False,
                        prompt_hash=prompt_hash,
                    )
                    if is_last_retry:
                        raise LLMGenerationError(
                            f"{self._node.value} output truncated; retries exhausted",
                            reason_code=ReasonCode.LLM_RETRY_LIMIT_EXCEEDED,
                        )
                    continue  # transient per axiom 22: retry within the cap
                self._append_row(
                    run_id=run_id,
                    plan_version=plan_version,
                    attempt=attempt,
                    sdk_retry=sdk_retry,
                    result=result,
                    started=started,
                    reason_code=ReasonCode.LLM_MALFORMED_OUTPUT,
                    truncated=False,
                    refusal=False,
                    prompt_hash=prompt_hash,
                )
                return "the response could not be parsed into the target schema"

            try:
                validated = self._contract.model_validate(result.payload)
                if post_validate is not None:
                    post_validate(validated)
            except (ValidationError, LLMNodeError, ValueError) as exc:
                self._append_row(
                    run_id=run_id,
                    plan_version=plan_version,
                    attempt=attempt,
                    sdk_retry=sdk_retry,
                    result=result,
                    started=started,
                    reason_code=ReasonCode.LLM_SCHEMA_REJECTED,
                    truncated=truncated,
                    refusal=False,
                    prompt_hash=prompt_hash,
                )
                return str(exc)

            self._append_row(
                run_id=run_id,
                plan_version=plan_version,
                attempt=attempt,
                sdk_retry=sdk_retry,
                result=result,
                started=started,
                reason_code=None,
                truncated=truncated,
                refusal=False,
                prompt_hash=prompt_hash,
            )
            return validated
        raise LLMGenerationError(  # structurally unreachable; loop returns or raises
            f"{self._node.value} retry loop exited without an outcome",
            reason_code=ReasonCode.LLM_RETRY_LIMIT_EXCEEDED,
        )

    def _append_row(
        self,
        *,
        run_id: str,
        plan_version: str | None,
        attempt: int,
        sdk_retry: int,
        result: TransportResult | None,
        started: Any,
        reason_code: ReasonCode | None,
        truncated: bool,
        refusal: bool,
        prompt_hash: str,
    ) -> None:
        now = self._clock.now()
        latency_ms = max(0, int((now - started).total_seconds() * 1000))
        input_tokens = result.input_tokens if result is not None else 0
        output_tokens = result.output_tokens if result is not None else 0
        raw_text = result.raw_text if result is not None else None
        cache_read = result.cache_read_tokens if result is not None else 0
        self._store.append(
            LlmCallLog(
                llm_call_log_id=self._ids.new_id("llmcall"),
                run_id=run_id,
                plan_version=plan_version,
                node=self._node,
                prompt_version=self._config.prompt_version,
                model_name=self._config.model_name,
                attempt=attempt,
                sdk_retry=sdk_retry,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_estimate_usd=self._config.estimate_cost_usd(
                    input_tokens=input_tokens, output_tokens=output_tokens
                ),
                latency_ms=latency_ms,
                validation_outcome=(
                    ValidationOutcome.FAIL if reason_code is not None else ValidationOutcome.PASS
                ),
                reason_code=reason_code,
                cache_hit=cache_read > 0,
                truncated=truncated,
                refusal=refusal,
                prompt_hash=prompt_hash,
                response_hash=_sha256(raw_text) if raw_text is not None else None,
                created_at=now,
            )
        )


_STRATEGIST_SYSTEM = (
    "You are the Curriculum Strategist for a deterministic career-preparation "
    "engine. Propose a structured syllabus for the inputs provided. Cover every "
    "listed weakness, stay within the strategy constraints (module count, "
    "priorities, total minutes), and cite source claims by id in "
    "source_claim_ids for any company-specific module. Return only the "
    "structured object."
)

_PLANNER_SYSTEM = (
    "You are the Execution Planner for a deterministic career-preparation "
    "engine. Decompose the validated syllabus into a task plan. Every task_id "
    "must be unique; dependencies may only reference task ids defined in the "
    "same plan; every syllabus module must be covered by at least one task. "
    "Never include a prerequisites_met field — the system computes that "
    "deterministically. Return only the structured object."
)

_REFLECTION_SYSTEM = (
    "You write a short, supportive progress summary from already-classified "
    "drift events. Describe behavior, never identity: no psychological labels "
    "of any kind. Do not re-classify drift or invent data — explain only what "
    "the classified events say. Return only the structured object."
)

_EXPLANATION_SYSTEM = (
    "You explain a deterministic validation outcome to the user in plain, "
    "friendly language. Do not change, soften, or second-guess the outcome; "
    "explain it. Describe behavior, never identity. Return only the "
    "structured object."
)


def _scan_prose(summary: str, detail: Sequence[str]) -> None:
    _ensure_no_psychological_labels(summary)
    for line in detail:
        _ensure_no_psychological_labels(line)


class AnthropicStrategist:
    """Real Strategist. Same surface as ``FixtureStrategist``."""

    def __init__(
        self,
        *,
        transport: AnthropicTransport,
        store: LlmCallLogStore,
        clock: Clock,
        id_generator: IdGenerator,
        config: AdapterConfig | None = None,
        debug_raw_sink: Callable[[str], None] | None = None,
    ) -> None:
        self._engine = _GenerationEngine(
            node=LlmNodeName.STRATEGIST,
            contract=SyllabusUnits,
            config=config or STRATEGIST_CONFIG,
            transport=transport,
            store=store,
            clock=clock,
            id_generator=id_generator,
            debug_raw_sink=debug_raw_sink,
        )

    def run(
        self,
        *,
        run_id: str,
        user_profile: UserProfile,
        source_claims: Sequence[SourceClaim] = (),
        strategy_constraints: StrategyConstraints | None = None,
        plan_version: str | None = None,
    ) -> SyllabusUnits:
        # Validate the input bundle at the boundary, exactly like the fixture.
        bundle = StrategistInput(
            user_profile=user_profile,
            source_claims=list(source_claims),
            strategy_constraints=strategy_constraints or StrategyConstraints(),
        )
        constraints = bundle.strategy_constraints

        def _constraints_hold(model: BaseModel) -> None:
            _check_against_constraints(cast(SyllabusUnits, model), constraints)

        result = self._engine.generate(
            run_id=run_id,
            plan_version=plan_version,
            system=_STRATEGIST_SYSTEM,
            user_prompt=f"Inputs:\n{_canonical_json(bundle)}",
            post_validate=_constraints_hold,
        )
        return cast(SyllabusUnits, result)


class AnthropicPlanner:
    """Real Planner. Same surface as ``FixturePlanner``."""

    def __init__(
        self,
        *,
        transport: AnthropicTransport,
        store: LlmCallLogStore,
        clock: Clock,
        id_generator: IdGenerator,
        config: AdapterConfig | None = None,
        debug_raw_sink: Callable[[str], None] | None = None,
    ) -> None:
        self._engine = _GenerationEngine(
            node=LlmNodeName.PLANNER,
            contract=TaskPlan,
            config=config or PLANNER_CONFIG,
            transport=transport,
            store=store,
            clock=clock,
            id_generator=id_generator,
            debug_raw_sink=debug_raw_sink,
        )

    def run(
        self,
        *,
        run_id: str,
        syllabus: SyllabusUnits,
        plan_version: str | None = None,
    ) -> TaskPlan:
        result = self._engine.generate(
            run_id=run_id,
            plan_version=plan_version,
            system=_PLANNER_SYSTEM,
            user_prompt=f"Validated syllabus:\n{_canonical_json(syllabus)}",
        )
        return cast(TaskPlan, result)


class AnthropicReflectionSummary:
    """Real reflection node. Explains classified drift; never classifies it."""

    def __init__(
        self,
        *,
        transport: AnthropicTransport,
        store: LlmCallLogStore,
        clock: Clock,
        id_generator: IdGenerator,
        config: AdapterConfig | None = None,
        debug_raw_sink: Callable[[str], None] | None = None,
    ) -> None:
        self._engine = _GenerationEngine(
            node=LlmNodeName.REFLECTION_SUMMARY,
            contract=ReflectionSummary,
            config=config or REFLECTION_CONFIG,
            transport=transport,
            store=store,
            clock=clock,
            id_generator=id_generator,
            debug_raw_sink=debug_raw_sink,
        )

    def run(
        self,
        *,
        run_id: str,
        drift_events: Sequence[DriftEvent],
        completion_rate: float | None = None,
        plan_version: str | None = None,
    ) -> ReflectionSummary:
        events_json = json.dumps(
            [e.model_dump(mode="json") for e in drift_events], sort_keys=True
        )
        rate_line = (
            f"\nRecent completion rate: {completion_rate}" if completion_rate is not None else ""
        )

        def _behavior_only(model: BaseModel) -> None:
            summary = cast(ReflectionSummary, model)
            _scan_prose(summary.summary, summary.detail)

        result = self._engine.generate(
            run_id=run_id,
            plan_version=plan_version,
            system=_REFLECTION_SYSTEM,
            user_prompt=f"Classified drift events:\n{events_json}{rate_line}",
            post_validate=_behavior_only,
        )
        return cast(ReflectionSummary, result)


class AnthropicUserFacingExplanation:
    """Real explanation node. Words a deterministic outcome; never alters it."""

    def __init__(
        self,
        *,
        transport: AnthropicTransport,
        store: LlmCallLogStore,
        clock: Clock,
        id_generator: IdGenerator,
        config: AdapterConfig | None = None,
        debug_raw_sink: Callable[[str], None] | None = None,
    ) -> None:
        self._engine = _GenerationEngine(
            node=LlmNodeName.USER_FACING_EXPLANATION,
            contract=UserExplanation,
            config=config or EXPLANATION_CONFIG,
            transport=transport,
            store=store,
            clock=clock,
            id_generator=id_generator,
            debug_raw_sink=debug_raw_sink,
        )

    def run(
        self,
        *,
        run_id: str,
        validation_result: ValidationResult,
        plan_version: str | None = None,
    ) -> UserExplanation:
        def _behavior_only(model: BaseModel) -> None:
            explanation = cast(UserExplanation, model)
            _scan_prose(explanation.summary, explanation.detail)

        result = self._engine.generate(
            run_id=run_id,
            plan_version=plan_version,
            system=_EXPLANATION_SYSTEM,
            user_prompt=f"Validation result:\n{_canonical_json(validation_result)}",
            post_validate=_behavior_only,
        )
        return cast(UserExplanation, result)
