"""Multi-cycle deterministic replay of the Phase 7 accountability pipeline.

Phase 7 test expectation: "deterministic replay tests proving the same
telemetry produces the same intervention sequence".
``tests/golden/test_accountability_scenarios.py`` replays a single evaluation;
this file proves the composed pipeline over a *sequence* — three observable
weeks of raw telemetry → state projection → policy decision → nudge delivery /
recovery proposal, with one shared id generator and audit store across cycles,
replayed from scratch.

Composing ``accountability`` with ``planning`` here mirrors the composition
root (operator CLIs); the src-level leaf-region boundary is untouched.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from agentic_calendar.accountability.checkin import CheckinStatus
from agentic_calendar.accountability.nudge_store import InMemoryNudgeStore
from agentic_calendar.accountability.nudges import NudgeDeliveryService
from agentic_calendar.accountability.policy_engine import evaluate_accountability
from agentic_calendar.accountability.projection import ProjectionInput
from agentic_calendar.common.clock import FrozenClock
from agentic_calendar.common.ids import DeterministicIdGenerator
from agentic_calendar.contracts.accountability_intervention import AccountabilityAction
from agentic_calendar.contracts.checkin_event import RecoveryAction
from agentic_calendar.contracts.common_types import FocusLevel, TaskCategory
from agentic_calendar.contracts.reason_codes import ReasonCode
from agentic_calendar.contracts.task_plan import Task, TaskPlan
from agentic_calendar.planning import LifecycleState, PlanVersion, propose_recovery_plan

from ._builders import build_contract, build_telemetry_event

#: One evaluation instant per weekly cycle, all outside default quiet hours.
CYCLE_TIMES = (
    datetime(2026, 5, 4, 12, 0, tzinfo=UTC),
    datetime(2026, 5, 11, 12, 0, tzinfo=UTC),
    datetime(2026, 5, 18, 12, 0, tzinfo=UTC),
)


def _active_plan() -> PlanVersion:
    task = Task(
        task_id="t1",
        module_id="m_t1",
        title="t1",
        estimated_duration_min=60,
        cognitive_load=3,
        category=TaskCategory.PRACTICE,
        required_focus_level=FocusLevel.MEDIUM,
    )
    plan = TaskPlan(plan_version="plan_v1", tasks=[task])
    return PlanVersion(
        plan_version="plan_v1",
        user_id="user_123",
        state=LifecycleState.ACTIVE,
        plan=plan,
        created_at=CYCLE_TIMES[0],
        updated_at=CYCLE_TIMES[0],
    )


def _input(events: list, scheduled: int, completed: int) -> ProjectionInput:
    return ProjectionInput(
        user_id="user_123",
        plan_id="plan_004",
        events_7d=events,
        events_14d=events,
        scheduled_minutes_due=scheduled,
        completed_minutes_due=completed,
    )


def _cycles() -> list[tuple[datetime, ProjectionInput]]:
    """Three observable weeks: clean → missed-task threshold → behind schedule."""
    clean = [build_telemetry_event(f"c{i}") for i in range(4)]
    two_missed = [build_telemetry_event(f"x{i}", completed=False) for i in range(2)] + [
        build_telemetry_event(f"d{i}") for i in range(2)
    ]
    behind = [build_telemetry_event(f"b{i}") for i in range(4)] + [
        build_telemetry_event("b_miss", completed=False)
    ]
    return [
        (CYCLE_TIMES[0], _input(clean, scheduled=240, completed=240)),  # no action
        (CYCLE_TIMES[1], _input(two_missed, scheduled=240, completed=220)),  # nudge
        (CYCLE_TIMES[2], _input(behind, scheduled=400, completed=300)),  # 25% behind
    ]


def _run_pipeline() -> list[dict[str, Any]]:
    """One full run from scratch: fresh ids, fresh stores, same telemetry."""
    ids = DeterministicIdGenerator()
    contract = build_contract()
    active = _active_plan()
    store = InMemoryNudgeStore()
    outputs: list[dict[str, Any]] = []
    for cycle_time, inp in _cycles():
        clock = FrozenClock(cycle_time)
        outcome = evaluate_accountability(
            inp, contract, CheckinStatus.NOT_REQUIRED, clock=clock, id_generator=ids
        )
        nudge = NudgeDeliveryService(clock=clock, id_generator=ids, store=store).maybe_deliver(
            decision=outcome.decision, contract=contract, tz=UTC
        )
        draft = diff = None
        if outcome.decision.action is AccountabilityAction.GENERATE_RECOVERY_PLAN_DRAFT:
            proposal = propose_recovery_plan(
                active, RecoveryAction.RESCHEDULE, id_generator=ids, clock=clock
            )
            assert proposal.draft is not None and proposal.diff is not None
            draft = proposal.draft.model_dump()
            diff = proposal.diff.model_dump()
        outputs.append(
            {
                "state": outcome.state.model_dump(),
                "decision": outcome.decision.model_dump(),
                "nudge": nudge.model_dump() if nudge is not None else None,
                "recovery_draft": draft,
                "recovery_diff": diff,
            }
        )
    return outputs


def test_same_telemetry_replays_identical_multi_cycle_sequence() -> None:
    assert _run_pipeline() == _run_pipeline()


def test_intervention_sequence_is_typed_and_ordered() -> None:
    """The sequence carries the expected typed reason codes, the nudge fires
    only at the missed-task cycle, and recovery speaks through a draft (the
    approval surface), never a nudge."""
    seq = _run_pipeline()
    assert [c["decision"]["action"] for c in seq] == [
        None,
        AccountabilityAction.SEND_USER_NUDGE,
        AccountabilityAction.GENERATE_RECOVERY_PLAN_DRAFT,
    ]
    assert [c["decision"]["reason_code"] for c in seq] == [
        None,
        ReasonCode.MISSED_TASK_THRESHOLD_REACHED,
        ReasonCode.BEHIND_SCHEDULE_THRESHOLD_REACHED,
    ]
    assert [c["nudge"] is not None for c in seq] == [False, True, False]
    assert [c["recovery_draft"] is not None for c in seq] == [False, False, True]
    # Every cycle's audit trail logs all five rule evaluations.
    assert all(len(c["decision"]["evaluations"]) == 5 for c in seq)


def test_disabling_contract_stops_interventions_and_leaves_plan_untouched() -> None:
    """Golden scenario 24, end to end: after the user disables the contract,
    worse telemetry produces no action and no audit-store growth, and the
    active plan version is byte-for-byte unaffected."""
    ids = DeterministicIdGenerator()
    store = InMemoryNudgeStore()
    active = _active_plan()
    plan_before = active.model_dump()

    active_contract = build_contract()
    clock1 = FrozenClock(CYCLE_TIMES[1])
    _, missed_input = _cycles()[1]
    outcome = evaluate_accountability(
        missed_input, active_contract, CheckinStatus.NOT_REQUIRED, clock=clock1, id_generator=ids
    )
    nudge = NudgeDeliveryService(clock=clock1, id_generator=ids, store=store).maybe_deliver(
        decision=outcome.decision, contract=active_contract, tz=UTC
    )
    assert nudge is not None

    inactive = build_contract(active=False)
    worse = _input(
        [build_telemetry_event(f"w{i}", completed=False) for i in range(5)],
        scheduled=400,
        completed=100,
    )
    clock2 = FrozenClock(CYCLE_TIMES[2])
    outcome2 = evaluate_accountability(
        worse, inactive, CheckinStatus.NOT_REQUIRED, clock=clock2, id_generator=ids
    )
    assert outcome2.decision.action is None
    assert outcome2.decision.reason_code is ReasonCode.ACCOUNTABILITY_CONTRACT_INACTIVE
    assert outcome2.decision.sponsor_action is None
    assert outcome2.state.recommended_intervention is None

    nudge2 = NudgeDeliveryService(clock=clock2, id_generator=ids, store=store).maybe_deliver(
        decision=outcome2.decision, contract=inactive, tz=UTC
    )
    assert nudge2 is None
    assert store.all() == [nudge]  # no growth after disable
    assert active.model_dump() == plan_before  # the active plan is unaffected
