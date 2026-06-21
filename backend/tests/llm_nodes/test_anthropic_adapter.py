"""Tests for the Anthropic adapters — fake transport, zero network."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import BaseModel

from agentic_calendar.common.clock import FrozenClock
from agentic_calendar.common.ids import DeterministicIdGenerator
from agentic_calendar.contracts.reason_codes import ReasonCode
from agentic_calendar.contracts.strategy_constraints import StrategyConstraints
from agentic_calendar.contracts.syllabus_units import SyllabusUnits
from agentic_calendar.contracts.user_profile import UserProfile
from agentic_calendar.contracts.validation_result import (
    ArtifactType,
    NextAction,
    ValidationResult,
    Violation,
)
from agentic_calendar.contracts.violation_types import ViolationType
from agentic_calendar.llm_nodes.anthropic_adapter import (
    AnthropicMessagesTransport,
    AnthropicPlanner,
    AnthropicReflectionSummary,
    AnthropicStrategist,
    LLMGenerationError,
    TransportError,
    TransportResult,
)
from agentic_calendar.llm_nodes.call_log import (
    InMemoryLlmCallLogStore,
    ValidationOutcome,
)
from tests._fixture_loader import iter_valid

_NOW = datetime(2026, 6, 10, 12, 0, tzinfo=UTC)

_VALID_PLAN: dict[str, Any] = {
    "plan_version": "plan_t_001",
    "tasks": [
        {
            "task_id": "dp_001",
            "module_id": "dp",
            "title": "Review DP state definitions",
            "dependencies": [],
            "estimated_duration_min": 60,
            "cognitive_load": 4,
            "category": "concept_review",
            "required_focus_level": "deep",
            "splittable": False,
        }
    ],
}

#: Parses as JSON but violates the TaskPlan contract (duplicate task_id) —
#: exactly the case schema-enforced generation cannot be trusted to prevent.
_INVALID_PLAN: dict[str, Any] = {
    "plan_version": "plan_t_bad",
    "tasks": [
        {**_VALID_PLAN["tasks"][0]},
        {**_VALID_PLAN["tasks"][0], "title": "Duplicate id"},
    ],
}

_SYLLABUS: dict[str, Any] = {
    "syllabus_version": "syl_t",
    "goal_summary": "Prepare for backend interviews.",
    "modules": [
        {
            "module_id": "dp",
            "title": "Dynamic Programming",
            "priority": "high",
            "reason": "Listed weakness.",
            "target_outcomes": ["Recognize DP state definitions"],
            "estimated_total_min": 720,
            "difficulty": 5,
            "source_claim_ids": ["claim_012"],
        }
    ],
}

_TWO_MODULE_SYLLABUS: dict[str, Any] = {
    "syllabus_version": "syl_t2",
    "goal_summary": "Prepare for backend interviews.",
    "modules": [
        _SYLLABUS["modules"][0],
        {**_SYLLABUS["modules"][0], "module_id": "api", "title": "API Design"},
    ],
}


class FakeTransport:
    """Replays a script of results/exceptions; records every request."""

    def __init__(self, script: list[TransportResult | Exception]) -> None:
        self._script = list(script)
        self.requests: list[dict[str, Any]] = []

    def complete(self, **kwargs: Any) -> TransportResult:
        self.requests.append(kwargs)
        if not self._script:
            raise AssertionError("FakeTransport script exhausted")
        item = self._script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _ok(payload: dict[str, Any] | None, *, stop_reason: str = "end_turn") -> TransportResult:
    return TransportResult(
        payload=payload,
        raw_text=json.dumps(payload) if payload is not None else "RAW_UNPARSEABLE",
        stop_reason=stop_reason,
        input_tokens=100,
        output_tokens=50,
    )


def _planner(
    script: list[TransportResult | Exception],
) -> tuple[AnthropicPlanner, InMemoryLlmCallLogStore, FakeTransport]:
    store = InMemoryLlmCallLogStore()
    transport = FakeTransport(script)
    planner = AnthropicPlanner(
        transport=transport,
        store=store,
        clock=FrozenClock(_NOW),
        id_generator=DeterministicIdGenerator(),
    )
    return planner, store, transport


def _run_planner(planner: AnthropicPlanner) -> BaseModel:
    return planner.run(
        run_id="run_t", syllabus=SyllabusUnits.model_validate(_SYLLABUS), plan_version="v1"
    )


def test_happy_path_returns_validated_plan_and_logs_one_complete_row() -> None:
    planner, store, transport = _planner([_ok(_VALID_PLAN)])
    plan = _run_planner(planner)
    assert plan.model_dump(mode="json")["plan_version"] == "plan_t_001"

    rows = store.list_all()
    assert len(rows) == 1
    row = rows[0]
    assert row.validation_outcome is ValidationOutcome.PASS
    assert row.reason_code is None
    assert row.run_id == "run_t"
    assert row.plan_version == "v1"
    assert row.node.value == "planner"
    assert row.prompt_version == "planner-v1-2026-06-10"
    assert row.model_name == "claude-haiku-4-5"
    assert (row.attempt, row.sdk_retry) == (0, 0)
    assert (row.input_tokens, row.output_tokens) == (100, 50)
    assert row.cost_estimate_usd == (100 * 1.00 + 50 * 5.00) / 1_000_000
    assert row.prompt_hash is not None and row.response_hash is not None
    assert row.cache_hit is False
    # Schema-enforced generation was requested with the target contract.
    assert transport.requests[0]["output_contract"].__name__ == "TaskPlan"


def test_transient_call_failure_retries_within_cap() -> None:
    planner, store, _ = _planner([TransportError("boom"), _ok(_VALID_PLAN)])
    _run_planner(planner)
    rows = store.list_all()
    assert [(r.attempt, r.sdk_retry) for r in rows] == [(0, 0), (0, 1)]
    assert rows[0].reason_code is ReasonCode.LLM_CALL_FAILED
    assert (rows[0].input_tokens, rows[0].output_tokens) == (0, 0)
    assert rows[1].validation_outcome is ValidationOutcome.PASS


def test_retry_exhaustion_raises_typed_code_and_logs_final_row() -> None:
    planner, store, _ = _planner([TransportError("a"), TransportError("b"), TransportError("c")])
    with pytest.raises(LLMGenerationError) as exc_info:
        _run_planner(planner)
    assert exc_info.value.reason_code is ReasonCode.LLM_RETRY_LIMIT_EXCEEDED
    rows = store.list_all()
    assert [r.sdk_retry for r in rows] == [0, 1, 2]
    assert [r.reason_code for r in rows] == [
        ReasonCode.LLM_CALL_FAILED,
        ReasonCode.LLM_CALL_FAILED,
        ReasonCode.LLM_RETRY_LIMIT_EXCEEDED,
    ]


def test_refusal_is_terminal_and_never_retried() -> None:
    planner, store, transport = _planner([_ok(None, stop_reason="refusal")])
    with pytest.raises(LLMGenerationError) as exc_info:
        _run_planner(planner)
    assert exc_info.value.reason_code is ReasonCode.LLM_REFUSAL
    assert len(transport.requests) == 1
    row = store.list_all()[0]
    assert row.refusal is True
    assert row.reason_code is ReasonCode.LLM_REFUSAL


def test_truncated_without_payload_retries_then_succeeds() -> None:
    planner, store, _ = _planner([_ok(None, stop_reason="max_tokens"), _ok(_VALID_PLAN)])
    _run_planner(planner)
    rows = store.list_all()
    assert rows[0].reason_code is ReasonCode.LLM_TRUNCATED
    assert rows[0].truncated is True
    assert (rows[1].attempt, rows[1].sdk_retry) == (0, 1)
    assert rows[1].validation_outcome is ValidationOutcome.PASS


def test_truncated_but_valid_payload_still_passes_with_flag() -> None:
    planner, store, _ = _planner([_ok(_VALID_PLAN, stop_reason="max_tokens")])
    _run_planner(planner)
    row = store.list_all()[0]
    assert row.validation_outcome is ValidationOutcome.PASS
    assert row.truncated is True


def test_malformed_output_triggers_repair_attempt() -> None:
    planner, store, transport = _planner([_ok(None), _ok(_VALID_PLAN)])
    _run_planner(planner)
    rows = store.list_all()
    assert rows[0].reason_code is ReasonCode.LLM_MALFORMED_OUTPUT
    assert [(r.attempt, r.sdk_retry) for r in rows] == [(0, 0), (1, 0)]
    assert "rejected by deterministic validation" in transport.requests[1]["user_prompt"]


def test_boundary_revalidation_rejects_enforced_output() -> None:
    """Schema-enforced output that violates the contract is still rejected
    (axiom 22: never trust the enforcement) and repaired with the violation."""
    planner, store, transport = _planner([_ok(_INVALID_PLAN), _ok(_VALID_PLAN)])
    plan = _run_planner(planner)
    assert plan.model_dump(mode="json")["plan_version"] == "plan_t_001"
    rows = store.list_all()
    assert rows[0].reason_code is ReasonCode.LLM_SCHEMA_REJECTED
    assert rows[1].validation_outcome is ValidationOutcome.PASS
    # The repair re-prompt carries the deterministic rejection, not prose.
    assert "rejected by deterministic validation" in transport.requests[1]["user_prompt"]


def test_repair_cap_exhaustion_routes_to_error() -> None:
    planner, store, _ = _planner([_ok(_INVALID_PLAN)] * 3)
    with pytest.raises(LLMGenerationError) as exc_info:
        _run_planner(planner)
    assert exc_info.value.reason_code is ReasonCode.REPAIR_LIMIT_EXCEEDED
    rows = store.list_all()
    assert [r.attempt for r in rows] == [0, 1, 2]
    assert all(r.reason_code is ReasonCode.LLM_SCHEMA_REJECTED for r in rows)


def test_cache_hit_flag_follows_provider_cache_reads() -> None:
    result = TransportResult(
        payload=_VALID_PLAN,
        raw_text=json.dumps(_VALID_PLAN),
        stop_reason="end_turn",
        input_tokens=100,
        output_tokens=50,
        cache_read_tokens=80,
    )
    planner, store, _ = _planner([result])
    _run_planner(planner)
    assert store.list_all()[0].cache_hit is True


def test_no_raw_content_persisted_in_any_row() -> None:
    planner, store, transport = _planner([_ok(_INVALID_PLAN), _ok(_VALID_PLAN)])
    _run_planner(planner)
    sent_prompt = transport.requests[0]["user_prompt"]
    sent_system = transport.requests[0]["system"]
    for row in store.list_all():
        dumped = json.dumps(row.model_dump(mode="json"))
        assert sent_prompt not in dumped
        assert sent_system not in dumped
        assert "Review DP state definitions" not in dumped  # response content


def test_debug_raw_sink_receives_raw_but_store_does_not() -> None:
    captured: list[str] = []
    store = InMemoryLlmCallLogStore()
    planner = AnthropicPlanner(
        transport=FakeTransport([_ok(_VALID_PLAN)]),
        store=store,
        clock=FrozenClock(_NOW),
        id_generator=DeterministicIdGenerator(),
        debug_raw_sink=captured.append,
    )
    _run_planner(planner)
    assert captured == [json.dumps(_VALID_PLAN)]
    assert "Review DP state definitions" not in json.dumps(
        [r.model_dump(mode="json") for r in store.list_all()]
    )


# --- Node-specific gates ---


def _profile() -> UserProfile:
    fixture = next(f for f in iter_valid("user_profile") if f.name == "backend_swe_intermediate")
    return UserProfile.model_validate(fixture.payload)


def test_planner_prompt_carries_profile_constraints_as_canonical_json() -> None:
    """With a profile, the planner prompt embeds the typed scheduling limits
    (the values user-fit validation enforces), derived only from the profile."""
    planner, _store, transport = _planner([_ok(_VALID_PLAN)])
    planner.run(
        run_id="run_t",
        syllabus=SyllabusUnits.model_validate(_SYLLABUS),
        plan_version="v1",
        user_profile=_profile(),
    )
    prompt = transport.requests[0]["user_prompt"]
    assert "Planning constraints (hard limits enforced by validation):" in prompt
    # backend_swe_intermediate fixture: max 120, preferred 60, 8h x 10wk.
    assert '"max_session_length_min": 120' in prompt
    assert '"preferred_session_length_min": 60' in prompt
    assert '"total_capacity_min": 4800' in prompt
    assert '"weekly_hours": 8.0' in prompt
    assert '"timeline_weeks": 10' in prompt
    assert '"splittable_rule"' in prompt


def test_planner_prompt_has_no_constraints_block_without_profile() -> None:
    planner, _store, transport = _planner([_ok(_VALID_PLAN)])
    _run_planner(planner)
    assert "Planning constraints" not in transport.requests[0]["user_prompt"]


def test_planner_prompt_embeds_repair_violations_and_reason_code() -> None:
    """A caller-supplied failed ValidationResult reaches the prompt as the
    typed violation type and reason_code — structured repair, not prose."""
    repair = ValidationResult(
        run_id="run_t",
        artifact_type=ArtifactType.TASK_PLAN,
        valid=False,
        repairable=True,
        reason_code=ReasonCode.USER_FIT_VIOLATED,
        violations=[
            Violation(
                type=ViolationType.DURATION_EXCEEDS_USER_MAX_SESSION,
                task_id="dp_001",
                details={"duration_min": 150, "max_session_length_min": 120},
            )
        ],
        repair_attempt=1,
        next_action=NextAction.PLANNER_REPAIR_RETRY,
    )
    planner, _store, transport = _planner([_ok(_VALID_PLAN)])
    planner.run(
        run_id="run_t",
        syllabus=SyllabusUnits.model_validate(_SYLLABUS),
        plan_version="v1",
        repair=repair,
    )
    prompt = transport.requests[0]["user_prompt"]
    assert "failed deterministic validation" in prompt
    assert ViolationType.DURATION_EXCEEDS_USER_MAX_SESSION.value in prompt
    assert ReasonCode.USER_FIT_VIOLATED.value in prompt


def test_strategist_constraint_violation_enters_repair_loop() -> None:
    store = InMemoryLlmCallLogStore()
    transport = FakeTransport([_ok(_TWO_MODULE_SYLLABUS), _ok(_SYLLABUS)])
    strategist = AnthropicStrategist(
        transport=transport,
        store=store,
        clock=FrozenClock(_NOW),
        id_generator=DeterministicIdGenerator(),
    )
    syllabus = strategist.run(
        run_id="run_t",
        user_profile=_profile(),
        strategy_constraints=StrategyConstraints(max_modules=1),
    )
    assert len(syllabus.modules) == 1
    rows = store.list_all()
    assert rows[0].reason_code is ReasonCode.LLM_SCHEMA_REJECTED
    assert "max_modules" in transport.requests[1]["user_prompt"]


def _profile_with_resume(text: str) -> UserProfile:
    fixture = next(f for f in iter_valid("user_profile") if f.name == "backend_swe_intermediate")
    return UserProfile.model_validate({**fixture.payload, "resume_text": text})


def _run_strategist_once(user_profile: UserProfile) -> FakeTransport:
    transport = FakeTransport([_ok(_SYLLABUS)])
    AnthropicStrategist(
        transport=transport,
        store=InMemoryLlmCallLogStore(),
        clock=FrozenClock(_NOW),
        id_generator=DeterministicIdGenerator(),
    ).run(run_id="run_t", user_profile=user_profile)
    return transport


def test_strategist_prompt_includes_resume_text_when_present() -> None:
    transport = _run_strategist_once(_profile_with_resume("ACME_RESUME_MARKER 4 yrs Go"))
    prompt = transport.requests[0]["user_prompt"]
    assert "Candidate résumé" in prompt
    assert "ACME_RESUME_MARKER 4 yrs Go" in prompt


def test_strategist_prompt_omits_resume_text_cleanly_when_none() -> None:
    # The default fixture profile has no résumé; the field must leave no artifact
    # in the prompt — not even the `resume_text` key or an empty section header.
    transport = _run_strategist_once(_profile())
    prompt = transport.requests[0]["user_prompt"]
    assert "resume_text" not in prompt
    assert "résumé" not in prompt.lower()


#: Parses as JSON but violates the SyllabusUnits contract: a high-priority
#: module with no ``reason`` (``SyllabusModule._high_priority_needs_reason``).
#: This is the live-dogfood failure that crashed propose with a raw 422.
_HIGH_PRIORITY_NO_REASON: dict[str, Any] = {
    "syllabus_version": "syl_bad",
    "goal_summary": "Prepare for backend interviews.",
    "modules": [
        {
            "module_id": "dp",
            "title": "Dynamic Programming",
            "priority": "high",
            # no "reason" key
            "target_outcomes": ["Recognize DP state definitions"],
            "estimated_total_min": 720,
            "difficulty": 5,
            "source_claim_ids": [],
        }
    ],
}


class _FakeMessagesResource:
    """Stand-in for ``client.messages``: ``create`` returns canned structured-
    output text and records every call's kwargs."""

    def __init__(self, text: str) -> None:
        self._text = text
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=self._text)],
            stop_reason="end_turn",
            usage=SimpleNamespace(input_tokens=100, output_tokens=50),
        )


class _FakeAnthropicClient:
    def __init__(self, text: str) -> None:
        self.messages = _FakeMessagesResource(text)


def test_transport_hands_engine_raw_output_without_validating() -> None:
    """Regression: the live transport must NOT eagerly validate. A contract-
    violating body comes back as the raw dict, not a raised ValidationError, so
    the engine's repair loop can see and repair it (the old ``messages.parse``
    path raised inside the SDK and escaped the loop as a 500/422)."""
    client = _FakeAnthropicClient(json.dumps(_HIGH_PRIORITY_NO_REASON))
    result = AnthropicMessagesTransport(client=client).complete(
        model_name="claude-opus-4-8",
        max_tokens=1024,
        system="s",
        user_prompt="p",
        output_contract=SyllabusUnits,
    )
    assert result.payload == _HIGH_PRIORITY_NO_REASON
    assert result.stop_reason == "end_turn"
    # Generation was still shaped to the contract's schema via output_config.
    sent = client.messages.calls[0]["output_config"]["format"]
    assert sent["type"] == "json_schema" and sent["schema"]


def test_strategist_contract_violation_repairs_then_typed_error() -> None:
    """End-to-end over the live transport: a syllabus that violates a contract
    invariant repairs within the bounded loop and ends as a typed
    REPAIR_LIMIT_EXCEEDED — never a raw ValidationError leaking to the caller."""
    client = _FakeAnthropicClient(json.dumps(_HIGH_PRIORITY_NO_REASON))
    store = InMemoryLlmCallLogStore()
    strategist = AnthropicStrategist(
        transport=AnthropicMessagesTransport(client=client),
        store=store,
        clock=FrozenClock(_NOW),
        id_generator=DeterministicIdGenerator(),
    )

    with pytest.raises(LLMGenerationError) as exc_info:
        strategist.run(run_id="run_t", user_profile=_profile())

    assert exc_info.value.reason_code is ReasonCode.REPAIR_LIMIT_EXCEEDED
    rows = store.list_all()
    assert [r.attempt for r in rows] == [0, 1, 2]
    assert all(r.reason_code is ReasonCode.LLM_SCHEMA_REJECTED for r in rows)
    # The repair re-prompt carried the specific deterministic violation.
    repair_prompt = client.messages.calls[1]["messages"][0]["content"]
    assert "rejected by deterministic validation" in repair_prompt
    assert "reason" in repair_prompt


def test_reflection_psych_label_is_rejected_and_repaired() -> None:
    """A contract-valid summary that labels identity never leaves the node."""
    store = InMemoryLlmCallLogStore()
    transport = FakeTransport(
        [
            _ok({"summary": "You have been lazy this week.", "detail": []}),
            _ok({"summary": "Practice tasks are taking longer than planned.", "detail": []}),
        ]
    )
    reflection = AnthropicReflectionSummary(
        transport=transport,
        store=store,
        clock=FrozenClock(_NOW),
        id_generator=DeterministicIdGenerator(),
    )
    summary = reflection.run(run_id="run_t", drift_events=[])
    assert "lazy" not in summary.summary
    rows = store.list_all()
    assert rows[0].reason_code is ReasonCode.LLM_SCHEMA_REJECTED
    assert rows[1].validation_outcome is ValidationOutcome.PASS
