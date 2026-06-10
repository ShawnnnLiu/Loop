"""Golden scenarios for the Phase 7 accountability layer
(docs/golden-test-cases.md, scenarios 16, 21, 22, 23, 24).

Each scenario runs the real pipeline end to end — telemetry windows →
deterministic projection → policy engine → nudge / recovery flow — and asserts
the exact typed ``reason_code``, the decision structure, that no sponsor
notification fires where the scenario forbids one, and that the active plan is
never mutated. Scenario 23 exercises the drift classifier's
``accountability_mismatch`` rule.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from agentic_calendar.accountability import (
    CheckinStatus,
    InMemoryNudgeStore,
    NudgeDeliveryService,
    ProjectionInput,
    derive_accountability_contract,
    evaluate_accountability,
    evaluate_checkin,
)
from agentic_calendar.common.clock import FrozenClock
from agentic_calendar.common.ids import DeterministicIdGenerator
from agentic_calendar.contracts.accountability_intervention import (
    AccountabilityAction,
)
from agentic_calendar.contracts.checkin_event import RecoveryAction
from agentic_calendar.contracts.common_types import Day, FocusLevel, TaskCategory
from agentic_calendar.contracts.drift_event import (
    DriftType,
    RecommendedPolicyAction,
)
from agentic_calendar.contracts.motivation_profile import NudgeChannel
from agentic_calendar.contracts.nudge import NudgeStatus
from agentic_calendar.contracts.reason_codes import ReasonCode
from agentic_calendar.contracts.task_plan import Task, TaskPlan
from agentic_calendar.drift import DriftClassifier, DriftInput
from agentic_calendar.planning import (
    LifecycleState,
    PlanVersion,
    RecoveryRoute,
    propose_recovery_plan,
)
from tests.accountability._builders import build_profile, build_telemetry_event

LA = ZoneInfo("America/Los_Angeles")
NOW = datetime(2026, 5, 11, 12, 0, tzinfo=LA)  # Monday noon local


def _evaluate(
    *,
    missed: int = 0,
    completed: int = 6,
    scheduled_due: int = 360,
    completed_due: int = 360,
    profile_overrides: dict | None = None,
    active: bool = True,
    checkin_status: CheckinStatus = CheckinStatus.NOT_REQUIRED,
    now: datetime = NOW,
):
    """Run derivation → projection → policy engine on a crafted week."""
    clock = FrozenClock(now)
    ids = DeterministicIdGenerator()
    profile = build_profile(
        sponsor_enabled=False,
        sponsor_visibility_level="none",
        sponsor_id=None,
        **(profile_overrides or {}),
    )
    contract = derive_accountability_contract(profile, id_generator=ids, clock=clock, active=active)
    events = [build_telemetry_event(f"done_{i}") for i in range(completed)] + [
        build_telemetry_event(f"miss_{i}", completed=False) for i in range(missed)
    ]
    outcome = evaluate_accountability(
        ProjectionInput(
            user_id=profile.user_id,
            plan_id="plan_004",
            events_7d=events,
            events_14d=events,
            scheduled_minutes_due=scheduled_due,
            completed_minutes_due=completed_due,
        ),
        contract,
        checkin_status,
        clock=clock,
        id_generator=ids,
    )
    return outcome, contract, clock, ids


def _deliver(outcome, contract, clock, ids):
    store = InMemoryNudgeStore()
    service = NudgeDeliveryService(clock=clock, id_generator=ids, store=store)
    record = service.maybe_deliver(decision=outcome.decision, contract=contract, tz=LA)
    return record, store


# -- Scenario 16: private nudge at missed-task threshold ---------------------------


def test_scenario_16_private_nudge_only() -> None:
    """2 missed tasks in 7 days → MISSED_TASK_THRESHOLD_REACHED, a private
    in-app nudge only, and no sponsor notification."""
    outcome, contract, clock, ids = _evaluate(missed=2, completed=4)
    decision = outcome.decision

    assert decision.reason_code is ReasonCode.MISSED_TASK_THRESHOLD_REACHED
    assert decision.action is AccountabilityAction.SEND_USER_NUDGE
    assert decision.sponsor_action is None  # no sponsor notification

    record, store = _deliver(outcome, contract, clock, ids)
    assert record is not None
    assert record.channel is NudgeChannel.IN_APP  # private, preferred channel
    assert record.status is NudgeStatus.SENT
    assert store.list_for_user(record.user_id) == [record]


# -- Scenario 21: weekly check-in due ------------------------------------------------


def test_scenario_21_checkin_due() -> None:
    """Check-in due but not completed → CHECKIN_DUE, a check-in prompt, and no
    recovery plan draft until the user responds or CHECKIN_MISSED fires."""
    clock = FrozenClock(NOW)
    ids = DeterministicIdGenerator()
    profile = build_profile(
        sponsor_enabled=False,
        sponsor_visibility_level="none",
        sponsor_id=None,
        weekly_checkin_enabled=True,
        weekly_checkin_day=Day.SUN,
        weekly_checkin_time="19:00",
    )
    contract = derive_accountability_contract(profile, id_generator=ids, clock=clock)

    assessment = evaluate_checkin(contract, [], now=NOW, tz=LA)
    assert assessment.status is CheckinStatus.DUE

    outcome, contract, clock, ids = _evaluate(
        profile_overrides={
            "weekly_checkin_enabled": True,
            "weekly_checkin_day": Day.SUN,
            "weekly_checkin_time": "19:00",
        },
        checkin_status=assessment.status,
    )
    assert outcome.decision.reason_code is ReasonCode.CHECKIN_DUE
    assert outcome.decision.action is AccountabilityAction.CREATE_WEEKLY_CHECKIN_PROMPT
    assert outcome.decision.action is not AccountabilityAction.GENERATE_RECOVERY_PLAN_DRAFT

    # ... until CHECKIN_MISSED fires after the grace window.
    past_grace = NOW + timedelta(hours=contract.checkin_grace_hours)
    late = evaluate_checkin(contract, [], now=past_grace, tz=LA)
    assert late.status is CheckinStatus.MISSED


# -- Scenario 22: behind-schedule recovery plan --------------------------------------


def test_scenario_22_recovery_plan_draft_never_mutates_active() -> None:
    """25% behind schedule → BEHIND_SCHEDULE_THRESHOLD_REACHED, a recovery plan
    draft, and the active plan is not mutated in place."""
    outcome, _, clock, ids = _evaluate(scheduled_due=360, completed_due=270)
    decision = outcome.decision
    assert outcome.state.behind_schedule_percent == 25
    assert decision.reason_code is ReasonCode.BEHIND_SCHEDULE_THRESHOLD_REACHED
    assert decision.action is AccountabilityAction.GENERATE_RECOVERY_PLAN_DRAFT

    active = PlanVersion(
        plan_version="plan_v1",
        user_id="user_123",
        state=LifecycleState.ACTIVE,
        plan=TaskPlan(
            plan_version="plan_v1",
            tasks=[
                Task(
                    task_id="t1",
                    module_id="m_t1",
                    title="t1",
                    estimated_duration_min=90,
                    cognitive_load=3,
                    category=TaskCategory.PRACTICE,
                    required_focus_level=FocusLevel.MEDIUM,
                )
            ],
        ),
        created_at=NOW,
        updated_at=NOW,
    )
    snapshot = active.model_dump()
    proposal = propose_recovery_plan(
        active, RecoveryAction.RESCHEDULE, id_generator=ids, clock=clock
    )
    assert proposal.route is RecoveryRoute.DETERMINISTIC_DRAFT
    assert proposal.draft is not None
    assert proposal.draft.state is LifecycleState.DRAFT
    assert proposal.draft.parent_plan_version == active.plan_version
    assert active.model_dump() == snapshot  # active untouched


# -- Scenario 23: accountability mismatch (drift) -------------------------------------


def test_scenario_23_accountability_mismatch_no_sponsor_notification() -> None:
    """Repeatedly behind while rejecting interventions → drift type
    accountability_mismatch, policy action revise_accountability_contract, and
    no sponsor notification."""
    tasks = [
        Task(
            task_id=f"t{i}",
            module_id=f"m_t{i}",
            title=f"t{i}",
            estimated_duration_min=60,
            cognitive_load=3,
            category=TaskCategory.PRACTICE,
            required_focus_level=FocusLevel.MEDIUM,
        )
        for i in range(3)
    ]
    events = [build_telemetry_event(f"t{i}", completed=False) for i in range(3)]
    classifier = DriftClassifier(
        clock=FrozenClock(datetime(2026, 5, 12, tzinfo=UTC)),
        id_generator=DeterministicIdGenerator(),
    )
    result = classifier.classify(
        DriftInput(
            plan=TaskPlan(plan_version="pv1", tasks=tasks),
            events=events,
            declined_interventions=2,
        )
    )
    mismatch = [e for e in result if e.drift_type is DriftType.ACCOUNTABILITY_MISMATCH]
    assert len(mismatch) == 1
    event = mismatch[0]
    assert event.reason_code is ReasonCode.ACCOUNTABILITY_MISMATCH
    assert event.recommended_policy_action is RecommendedPolicyAction.REVISE_ACCOUNTABILITY_CONTRACT
    assert all(e.reason_code is not ReasonCode.SPONSOR_REPORT_PENDING for e in result)


# -- Scenario 24: accountability contract disabled ------------------------------------


def test_scenario_24_disabled_contract_stops_everything() -> None:
    """Disabling the contract → ACCOUNTABILITY_CONTRACT_INACTIVE, no further
    sponsor reports or nudges, and the active plan is unaffected."""
    outcome, contract, clock, ids = _evaluate(
        missed=6, completed=0, scheduled_due=360, completed_due=0, active=False
    )
    decision = outcome.decision
    assert decision.reason_code is ReasonCode.ACCOUNTABILITY_CONTRACT_INACTIVE
    assert decision.action is None
    assert decision.sponsor_action is None
    assert decision.sponsor_reason_code is ReasonCode.ACCOUNTABILITY_CONTRACT_INACTIVE
    assert decision.evaluations == []

    record, store = _deliver(outcome, contract, clock, ids)
    assert record is None
    assert store.all() == []


# -- Deterministic replay (Phase 7 test expectation) -----------------------------------


def test_same_telemetry_produces_same_intervention_sequence() -> None:
    """Replaying identical telemetry yields an identical state and decision."""
    a, *_ = _evaluate(missed=2, completed=4, completed_due=295)
    b, *_ = _evaluate(missed=2, completed=4, completed_due=295)
    assert a.state == b.state
    assert a.decision == b.decision
