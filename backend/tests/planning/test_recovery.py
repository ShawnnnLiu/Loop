"""Tests for the deterministic recovery-plan path (Phase 7, golden scenario 22)."""

from __future__ import annotations

from datetime import UTC, datetime

from agentic_calendar.common.clock import FrozenClock
from agentic_calendar.common.ids import DeterministicIdGenerator
from agentic_calendar.contracts.checkin_event import RecoveryAction
from agentic_calendar.contracts.common_types import FocusLevel, TaskCategory
from agentic_calendar.contracts.reason_codes import ReasonCode
from agentic_calendar.contracts.task_plan import Task, TaskPlan
from agentic_calendar.planning import (
    LifecycleState,
    PlanVersion,
    RecoveryRoute,
    propose_recovery_plan,
)

TS = datetime(2026, 5, 12, tzinfo=UTC)


def _task(tid: str) -> Task:
    return Task(
        task_id=tid,
        module_id=f"m_{tid}",
        title=tid,
        estimated_duration_min=90,
        cognitive_load=3,
        category=TaskCategory.PRACTICE,
        required_focus_level=FocusLevel.MEDIUM,
    )


def _active_plan() -> PlanVersion:
    plan = TaskPlan(plan_version="plan_v1", tasks=[_task("t1"), _task("t2")])
    return PlanVersion(
        plan_version="plan_v1",
        user_id="u1",
        state=LifecycleState.ACTIVE,
        plan=plan,
        created_at=TS,
        updated_at=TS,
    )


def _propose(active: PlanVersion, mode: RecoveryAction):
    return propose_recovery_plan(
        active,
        mode,
        id_generator=DeterministicIdGenerator(),
        clock=FrozenClock(TS),
    )


def test_reschedule_builds_draft_without_mutating_active() -> None:
    """Scenario 22: a recovery draft exists and the active plan is untouched."""
    active = _active_plan()
    before = active.model_dump()
    proposal = _propose(active, RecoveryAction.RESCHEDULE)

    assert proposal.route is RecoveryRoute.DETERMINISTIC_DRAFT
    assert proposal.reason_code is ReasonCode.RECOVERY_PLAN_REQUIRED
    assert proposal.draft is not None
    assert proposal.draft.state is LifecycleState.DRAFT
    assert proposal.draft.parent_plan_version == active.plan_version
    assert proposal.draft.plan_version != active.plan_version
    assert active.model_dump() == before  # never in-place mutation


def test_reschedule_preserves_task_content() -> None:
    active = _active_plan()
    proposal = _propose(active, RecoveryAction.RESCHEDULE)
    assert proposal.draft is not None
    drafted = [t.model_dump(exclude={"task_id"}) for t in proposal.draft.plan.tasks]
    original = [t.model_dump(exclude={"task_id"}) for t in active.plan.tasks]
    assert drafted == original
    assert [t.task_id for t in proposal.draft.plan.tasks] == [t.task_id for t in active.plan.tasks]


def test_reschedule_diff_is_honestly_zero_change() -> None:
    """The draft changes placement, not content; the diff must not fabricate
    rescheduled-task counts before the Scheduler has run."""
    proposal = _propose(_active_plan(), RecoveryAction.RESCHEDULE)
    assert proposal.diff is not None
    summary = proposal.diff.summary
    assert summary.tasks_added == 0
    assert summary.tasks_removed == 0
    assert summary.tasks_rescheduled == 0
    assert summary.tasks_with_duration_changes == 0
    assert proposal.diff.from_plan_version == "plan_v1"
    assert proposal.diff.to_plan_version == proposal.draft.plan_version


def test_content_modes_route_to_planner() -> None:
    """Deterministic code must not invent plan content (LLMs propose)."""
    for mode in (RecoveryAction.SCOPE_REDUCTION, RecoveryAction.EXTEND_TIMELINE):
        proposal = _propose(_active_plan(), mode)
        assert proposal.route is RecoveryRoute.PLANNER_REQUIRED
        assert proposal.mode is mode
        assert proposal.reason_code is ReasonCode.RECOVERY_PLAN_REQUIRED
        assert proposal.draft is None
        assert proposal.diff is None


def test_proposal_is_deterministic() -> None:
    a = _propose(_active_plan(), RecoveryAction.RESCHEDULE)
    b = _propose(_active_plan(), RecoveryAction.RESCHEDULE)
    assert a.draft is not None and b.draft is not None
    assert a.draft.model_dump() == b.draft.model_dump()
    assert a.diff.model_dump() == b.diff.model_dump()
