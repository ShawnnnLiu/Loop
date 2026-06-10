"""Tests for the recommitment flow (request/answer, answer-once, routing)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from agentic_calendar.accountability.recommitment import (
    RECOMMITMENT_CHOICE_TO_RECOVERY_MODE,
    InMemoryRecommitmentStore,
    RecommitmentAlreadyAnsweredError,
    RecommitmentRequestNotFoundError,
    record_recommitment,
    request_recommitment,
)
from agentic_calendar.common.clock import FrozenClock
from agentic_calendar.common.ids import DeterministicIdGenerator
from agentic_calendar.contracts.accountability_intervention import (
    AccountabilityAction,
    InterventionDecision,
    PolicyRuleEvaluation,
)
from agentic_calendar.contracts.checkin_event import RecoveryAction
from agentic_calendar.contracts.reason_codes import ReasonCode
from agentic_calendar.contracts.recommitment import (
    RecommitmentChoice,
    RecommitmentEvent,
)

T = datetime(2026, 5, 10, 20, 0, tzinfo=UTC)


def _evaluations(matched: str) -> list[PolicyRuleEvaluation]:
    return [
        PolicyRuleEvaluation(
            policy_name=name,
            matched=name == matched,
            observed_value=0.0,
            threshold_value=1.0,
        )
        for name in (
            "missed_task_warning",
            "recovery_plan",
            "weekly_checkin_required",
            "scope_reduction",
            "sponsor_summary",
        )
    ]


def _nudge_decision() -> InterventionDecision:
    return InterventionDecision(
        decision_id="intv_1",
        user_id="user_123",
        plan_id="plan_004",
        contract_id="acct_1",
        action=AccountabilityAction.SEND_USER_NUDGE,
        reason_code=ReasonCode.MISSED_TASK_THRESHOLD_REACHED,
        policy_name="missed_task_warning",
        sponsor_action=None,
        sponsor_reason_code=None,
        evaluations=_evaluations("missed_task_warning"),
        decided_at=T,
    )


def _flow():
    return InMemoryRecommitmentStore(), FrozenClock(T), DeterministicIdGenerator()


def test_request_is_persisted_with_typed_reason() -> None:
    store, clock, ids = _flow()
    request = request_recommitment(
        _nudge_decision(),
        plan_version="plan_004",
        store=store,
        clock=clock,
        id_generator=ids,
    )
    assert request.reason_code is ReasonCode.USER_RECOMMITMENT_REQUIRED
    assert store.all_requests() == [request]


def test_request_rejects_non_escalation_decision() -> None:
    store, clock, ids = _flow()
    decision = InterventionDecision(
        decision_id="intv_2",
        user_id="user_123",
        plan_id="plan_004",
        contract_id="acct_1",
        action=AccountabilityAction.CREATE_WEEKLY_CHECKIN_PROMPT,
        reason_code=ReasonCode.CHECKIN_DUE,
        policy_name="weekly_checkin_required",
        sponsor_action=None,
        sponsor_reason_code=None,
        evaluations=_evaluations("weekly_checkin_required"),
        decided_at=T,
    )
    with pytest.raises(ValueError, match="direct"):
        request_recommitment(
            decision, plan_version="plan_004", store=store, clock=clock, id_generator=ids
        )


def test_answer_recorded_once() -> None:
    store, clock, ids = _flow()
    request = request_recommitment(
        _nudge_decision(),
        plan_version="plan_004",
        store=store,
        clock=clock,
        id_generator=ids,
    )
    event = record_recommitment(
        request,
        RecommitmentChoice.KEEP_PLAN,
        store=store,
        clock=clock,
        id_generator=ids,
    )
    assert store.event_for_request(request.recommitment_request_id) == event
    with pytest.raises(RecommitmentAlreadyAnsweredError):
        record_recommitment(
            request,
            RecommitmentChoice.REVISE_TIMELINE,
            store=store,
            clock=clock,
            id_generator=ids,
        )


def test_answer_requires_known_request() -> None:
    store, _, _ = _flow()
    orphan = RecommitmentEvent(
        recommitment_event_id="recommit_evt_x",
        recommitment_request_id="recommit_req_unknown",
        user_id="user_123",
        plan_version="plan_004",
        choice=RecommitmentChoice.KEEP_PLAN,
        created_at=T,
    )
    with pytest.raises(RecommitmentRequestNotFoundError):
        store.append_event(orphan)


def test_choice_routing_matches_spec_table() -> None:
    """revise_timeline → extend_timeline; revise_intensity → scope_reduction.
    keep_plan and revise_goal route outside recovery, so they are absent."""
    assert RECOMMITMENT_CHOICE_TO_RECOVERY_MODE == {
        RecommitmentChoice.REVISE_TIMELINE: RecoveryAction.EXTEND_TIMELINE,
        RecommitmentChoice.REVISE_INTENSITY: RecoveryAction.SCOPE_REDUCTION,
    }
    assert RecommitmentChoice.KEEP_PLAN not in RECOMMITMENT_CHOICE_TO_RECOVERY_MODE
    assert RecommitmentChoice.REVISE_GOAL not in RECOMMITMENT_CHOICE_TO_RECOVERY_MODE
