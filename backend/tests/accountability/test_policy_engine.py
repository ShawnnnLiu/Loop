"""Tests for the Accountability Policy Engine.

Golden scenarios 16, 21, 22, 24 (and the 17/18 sponsor-lane splits) plus the
axiom 21 audit requirement: every rule evaluation is logged, and replaying the
same inputs produces the same decision.
"""

from __future__ import annotations

from datetime import UTC, datetime

from agentic_calendar.accountability.checkin import CheckinStatus
from agentic_calendar.accountability.policy_engine import (
    AccountabilityPolicyEngine,
    evaluate_accountability,
)
from agentic_calendar.accountability.projection import ProjectionInput
from agentic_calendar.common.clock import FrozenClock
from agentic_calendar.contracts.accountability_intervention import (
    AccountabilityAction,
)
from agentic_calendar.contracts.accountability_state import AccountabilityState
from agentic_calendar.contracts.common_types import AccountabilityStatus, Day
from agentic_calendar.contracts.motivation_profile import SponsorVisibility
from agentic_calendar.contracts.reason_codes import ReasonCode

from ._builders import build_contract, build_telemetry_event

T = datetime(2026, 5, 10, 20, 0, tzinfo=UTC)


def _engine() -> AccountabilityPolicyEngine:
    from agentic_calendar.common.ids import DeterministicIdGenerator

    return AccountabilityPolicyEngine(clock=FrozenClock(T), id_generator=DeterministicIdGenerator())


def _state(**overrides: object) -> AccountabilityState:
    base: dict[str, object] = {
        "user_id": "user_123",
        "plan_id": "plan_004",
        "completion_rate_7d": 0.8,
        "completion_rate_14d": 0.8,
        "missed_tasks_7d": 0,
        "reschedule_count_7d": 0,
        "behind_schedule_percent": 0,
        "weekly_checkin_completed": True,
        "current_status": AccountabilityStatus.ON_TRACK,
        "recommended_intervention": None,
        "sponsor_report_allowed": False,
        "sponsor_report_level": SponsorVisibility.NONE,
        "computed_at": T,
    }
    base.update(overrides)
    return AccountabilityState.model_validate(base)


def _decide(state: AccountabilityState, contract=None, checkin=CheckinStatus.COMPLETED):
    return _engine().decide(state, contract or build_contract(), checkin)


# -- golden scenario 16: private nudge at missed-task threshold -------------------


def test_scenario_16_private_nudge_only_no_sponsor() -> None:
    state = _state(missed_tasks_7d=2, current_status=AccountabilityStatus.SLIGHTLY_BEHIND)
    decision = _decide(state)
    assert decision.action is AccountabilityAction.SEND_USER_NUDGE
    assert decision.reason_code is ReasonCode.MISSED_TASK_THRESHOLD_REACHED
    assert decision.policy_name == "missed_task_warning"
    assert decision.sponsor_action is None
    assert decision.sponsor_reason_code is None


# -- golden scenario 17/18 sponsor-lane splits ------------------------------------


def test_scenario_17_sponsor_lane_fires_alongside_private_nudge() -> None:
    contract = build_contract(
        sponsor_reporting_allowed=True,
        sponsor_visibility_level=SponsorVisibility.SUMMARY_ONLY,
        sponsor_id="sponsor_001",
    )
    state = _state(
        missed_tasks_7d=4,
        current_status=AccountabilityStatus.BEHIND,
        sponsor_report_allowed=True,
        sponsor_report_level=SponsorVisibility.SUMMARY_ONLY,
    )
    decision = _decide(state, contract)
    assert decision.action is AccountabilityAction.SEND_USER_NUDGE
    assert decision.sponsor_action is AccountabilityAction.GENERATE_SPONSOR_SUMMARY_DRAFT
    assert decision.sponsor_reason_code is ReasonCode.SPONSOR_REPORT_PENDING


def test_scenario_18_sponsor_disabled_no_sponsor_draft() -> None:
    state = _state(missed_tasks_7d=4, current_status=AccountabilityStatus.BEHIND)
    decision = _decide(state)
    assert decision.action is AccountabilityAction.SEND_USER_NUDGE
    assert decision.sponsor_action is None
    sponsor_eval = decision.evaluations[-1]
    assert sponsor_eval.policy_name == "sponsor_summary"
    assert sponsor_eval.matched is False


# -- golden scenario 21: check-in due, nothing else firing ------------------------


def _checkin_contract():
    return build_contract(
        weekly_checkin_enabled=True, weekly_checkin_day=Day.SUN, weekly_checkin_time="19:00"
    )


def test_scenario_21_checkin_due_prompts_without_recovery_draft() -> None:
    state = _state(weekly_checkin_completed=False)
    decision = _decide(state, _checkin_contract(), checkin=CheckinStatus.DUE)
    assert decision.action is AccountabilityAction.CREATE_WEEKLY_CHECKIN_PROMPT
    assert decision.reason_code is ReasonCode.CHECKIN_DUE
    recovery = next(e for e in decision.evaluations if e.policy_name == "recovery_plan")
    assert recovery.matched is False


def test_checkin_missed_escalates_reason_code_only() -> None:
    state = _state(weekly_checkin_completed=False)
    decision = _decide(state, _checkin_contract(), checkin=CheckinStatus.MISSED)
    assert decision.action is AccountabilityAction.CREATE_WEEKLY_CHECKIN_PROMPT
    assert decision.reason_code is ReasonCode.CHECKIN_MISSED


def test_checkin_rule_suppressed_when_checkins_disabled() -> None:
    """A disabled cadence never prompts, even on an inconsistent DUE status."""
    state = _state(weekly_checkin_completed=False)
    decision = _decide(state, checkin=CheckinStatus.DUE)
    assert decision.action is None
    assert decision.reason_code is None
    checkin = next(e for e in decision.evaluations if e.policy_name == "weekly_checkin_required")
    assert checkin.matched is False


# -- golden scenario 22: behind-schedule recovery plan ----------------------------


def test_scenario_22_behind_schedule_selects_recovery_draft() -> None:
    state = _state(behind_schedule_percent=25, current_status=AccountabilityStatus.BEHIND)
    decision = _decide(state)
    assert decision.action is AccountabilityAction.GENERATE_RECOVERY_PLAN_DRAFT
    assert decision.reason_code is ReasonCode.BEHIND_SCHEDULE_THRESHOLD_REACHED


# -- golden scenario 24: contract disabled ----------------------------------------


def test_scenario_24_inactive_contract_short_circuits_both_lanes() -> None:
    contract = build_contract(active=False)
    state = _state(missed_tasks_7d=6, behind_schedule_percent=50)
    decision = _decide(state, contract)
    assert decision.action is None
    assert decision.reason_code is ReasonCode.ACCOUNTABILITY_CONTRACT_INACTIVE
    assert decision.sponsor_action is None
    assert decision.sponsor_reason_code is ReasonCode.ACCOUNTABILITY_CONTRACT_INACTIVE
    assert decision.evaluations == []


# -- ordering, audit, determinism ---------------------------------------------------


def test_first_match_wins_in_axiom_order() -> None:
    """Missed-task warning precedes recovery even when both fire."""
    state = _state(
        missed_tasks_7d=3,
        behind_schedule_percent=30,
        current_status=AccountabilityStatus.BEHIND,
    )
    decision = _decide(state)
    assert decision.policy_name == "missed_task_warning"
    fired = [e.policy_name for e in decision.evaluations if e.matched]
    assert fired == ["missed_task_warning", "recovery_plan"]


def test_every_rule_evaluation_is_logged_in_order() -> None:
    decision = _decide(_state())
    assert [e.policy_name for e in decision.evaluations] == [
        "missed_task_warning",
        "recovery_plan",
        "weekly_checkin_required",
        "scope_reduction",
        "sponsor_summary",
    ]


def test_scope_reduction_fires_on_low_14d_rate() -> None:
    state = _state(completion_rate_14d=0.4, current_status=AccountabilityStatus.SLIGHTLY_BEHIND)
    decision = _decide(state)
    assert decision.action is AccountabilityAction.SUGGEST_SCOPE_REDUCTION
    assert decision.reason_code is ReasonCode.LOW_COMPLETION_RATE


def test_no_intervention_when_nothing_fires() -> None:
    decision = _decide(_state())
    assert decision.action is None
    assert decision.reason_code is None
    assert all(not e.matched for e in decision.evaluations)


def test_same_inputs_same_decision_sequence() -> None:
    """Deterministic replay (Phase 7 test expectation)."""
    state = _state(missed_tasks_7d=2, current_status=AccountabilityStatus.SLIGHTLY_BEHIND)
    a = _decide(state)
    b = _decide(state)
    assert a == b


# -- composed evaluation -------------------------------------------------------------


def test_evaluate_accountability_fills_recommendation() -> None:
    from agentic_calendar.common.ids import DeterministicIdGenerator

    events = [build_telemetry_event(f"m{i}", completed=False) for i in range(2)] + [
        build_telemetry_event("d1"),
        build_telemetry_event("d2"),
    ]
    outcome = evaluate_accountability(
        ProjectionInput(
            user_id="user_123",
            plan_id="plan_004",
            events_7d=events,
            events_14d=events,
            scheduled_minutes_due=360,
            completed_minutes_due=300,
        ),
        build_contract(),
        CheckinStatus.NOT_REQUIRED,
        clock=FrozenClock(T),
        id_generator=DeterministicIdGenerator(),
    )
    assert outcome.decision.action is AccountabilityAction.SEND_USER_NUDGE
    assert outcome.state.recommended_intervention is AccountabilityAction.SEND_USER_NUDGE
    assert outcome.state.missed_tasks_7d == 2
