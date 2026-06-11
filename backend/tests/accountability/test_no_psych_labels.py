"""No psychological labels in any stored Phase 7 record (axiom 07 §19B).

The system must not store labels such as "lazy", "irresponsible", "anxious",
"avoidant", or "unmotivated" — behavioral state only. The privacy filter
already guards the sponsor surface; this file proves the invariant
structurally for everything Phase 7 itself persists: contract, projected
state, decisions, nudge records, and check-in events.
"""

from __future__ import annotations

from datetime import UTC, datetime

from agentic_calendar.accountability.checkin import CheckinStatus
from agentic_calendar.accountability.nudge_store import InMemoryNudgeStore
from agentic_calendar.accountability.nudges import NudgeDeliveryService
from agentic_calendar.accountability.policy_engine import evaluate_accountability
from agentic_calendar.accountability.projection import ProjectionInput
from agentic_calendar.common.clock import FrozenClock
from agentic_calendar.common.ids import DeterministicIdGenerator
from agentic_calendar.contracts.accountability_contract import AccountabilityContract
from agentic_calendar.contracts.accountability_intervention import (
    InterventionDecision,
    PolicyRuleEvaluation,
)
from agentic_calendar.contracts.accountability_state import AccountabilityState
from agentic_calendar.contracts.checkin_event import CheckinEvent
from agentic_calendar.contracts.nudge import NudgeRecord

from ._builders import build_checkin_event, build_contract, build_telemetry_event

#: Axiom 07 §19B's forbidden labels, plus field-name shapes that would smuggle
#: an inferred diagnosis into a stored record.
FORBIDDEN_LABELS = ("lazy", "irresponsible", "anxious", "avoidant", "unmotivated")
FORBIDDEN_FIELD_TERMS = ("psych", "diagnos", "personality", "emotion", "mood", *FORBIDDEN_LABELS)

#: Free-text field names a nudge record must never grow: wording is rendered
#: elsewhere (LLM-touchable) and is never control-plane or audit state.
FREE_TEXT_FIELD_NAMES = {"message", "text", "body", "wording", "content", "note", "comment"}

PHASE_7_STORED_MODELS = (
    AccountabilityContract,
    AccountabilityState,
    InterventionDecision,
    PolicyRuleEvaluation,
    NudgeRecord,
    CheckinEvent,
)

T = datetime(2026, 5, 11, 12, 0, tzinfo=UTC)


def test_no_psych_terms_in_stored_model_field_names() -> None:
    for model in PHASE_7_STORED_MODELS:
        for field_name in model.model_fields:
            lowered = field_name.lower()
            offending = [term for term in FORBIDDEN_FIELD_TERMS if term in lowered]
            assert not offending, f"{model.__name__}.{field_name} smuggles {offending}"


def test_nudge_record_carries_no_free_text_fields() -> None:
    assert not FREE_TEXT_FIELD_NAMES & set(NudgeRecord.model_fields)


def test_pipeline_outputs_carry_no_psychological_labels() -> None:
    """Run a worst-case week (misses, nudge fired) and scan every value the
    pipeline persists; behavior is recorded, identity never is."""
    ids = DeterministicIdGenerator()
    clock = FrozenClock(T)
    contract = build_contract()
    events = [build_telemetry_event(f"x{i}", completed=False) for i in range(2)] + [
        build_telemetry_event(f"d{i}") for i in range(2)
    ]
    outcome = evaluate_accountability(
        ProjectionInput(
            user_id="user_123",
            plan_id="plan_004",
            events_7d=events,
            events_14d=events,
            scheduled_minutes_due=240,
            completed_minutes_due=220,
        ),
        contract,
        CheckinStatus.NOT_REQUIRED,
        clock=clock,
        id_generator=ids,
    )
    store = InMemoryNudgeStore()
    nudge = NudgeDeliveryService(clock=clock, id_generator=ids, store=store).maybe_deliver(
        decision=outcome.decision, contract=contract, tz=UTC
    )
    assert nudge is not None

    dumps = [
        contract.model_dump_json(),
        outcome.state.model_dump_json(),
        outcome.decision.model_dump_json(),
        nudge.model_dump_json(),
        build_checkin_event().model_dump_json(),
    ]
    for dump in dumps:
        lowered = dump.lower()
        offending = [label for label in FORBIDDEN_LABELS if label in lowered]
        assert not offending, f"stored record contains forbidden labels {offending}: {dump}"
