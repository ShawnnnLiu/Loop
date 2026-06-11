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


# -- the draft flows through validation and approval before any calendar change ----
#
# Phase 7 test expectation: "recovery-plan tests that prove the draft goes
# through validation and approval before any calendar change". These compose
# planning with validation and the Calendar Write Manager the way the
# composition root does; src-level region boundaries are untouched.


def _coverage_valid_active_plan() -> PlanVersion:
    from tests.validation._helpers import make_plan, make_task

    plan = make_plan(
        make_task(task_id="dp_001", module_id="dp"),
        make_task(task_id="api_001", module_id="api_design"),
        plan_version="plan_v1",
    )
    return PlanVersion(
        plan_version="plan_v1",
        user_id="u1",
        state=LifecycleState.ACTIVE,
        plan=plan,
        created_at=TS,
        updated_at=TS,
    )


def test_recovery_draft_passes_full_validation() -> None:
    from agentic_calendar.contracts.validation_result import NextAction
    from agentic_calendar.validation import validate_task_plan
    from tests.validation._helpers import load_syllabus, load_user_profile

    proposal = _propose(_coverage_valid_active_plan(), RecoveryAction.RESCHEDULE)
    assert proposal.draft is not None
    result = validate_task_plan(
        proposal.draft.plan,
        syllabus=load_syllabus(),
        user_profile=load_user_profile(),
        run_id="run_recovery",
    )
    assert result.valid is True
    assert result.violations == []
    assert result.next_action is NextAction.SCHEDULER


def _recovery_draft_schedule():
    from agentic_calendar.contracts.draft_schedule import (
        DraftSchedule,
        DraftScheduleEntry,
    )

    proposal = _propose(_coverage_valid_active_plan(), RecoveryAction.RESCHEDULE)
    assert proposal.draft is not None
    start = datetime(2026, 5, 13, 18, 0, tzinfo=UTC)
    entries = tuple(
        DraftScheduleEntry(
            task_id=task.task_id,
            start=start.replace(hour=18 + i * 2),
            end=start.replace(hour=19 + i * 2),
        )
        for i, task in enumerate(proposal.draft.plan.tasks)
    )
    return DraftSchedule(
        draft_schedule_id="draft_recovery_1",
        plan_version=proposal.draft.plan_version,
        entries=entries,
        created_at=TS,
    )


def _write_manager():
    from agentic_calendar.approval.store import InMemoryApprovalEventStore
    from agentic_calendar.calendar_writer.in_memory_adapter import (
        InMemoryCalendarAdapter,
    )
    from agentic_calendar.calendar_writer.lock import CalendarWriteLockManager
    from agentic_calendar.calendar_writer.manager import CalendarWriteManager
    from agentic_calendar.calendar_writer.store import (
        InMemoryCalendarEventMappingStore,
    )

    clock = FrozenClock(TS)
    id_gen = DeterministicIdGenerator()
    adapter = InMemoryCalendarAdapter(id_generator=id_gen)
    approval_store = InMemoryApprovalEventStore()
    manager = CalendarWriteManager(
        adapter=adapter,
        mapping_store=InMemoryCalendarEventMappingStore(),
        approval_store=approval_store,
        lock_manager=CalendarWriteLockManager(clock=clock),
        id_generator=id_gen,
        clock=clock,
    )
    return manager, adapter, approval_store


def test_recovery_draft_write_blocked_without_approval() -> None:
    from agentic_calendar.calendar_writer.manager import WriteStatus

    manager, adapter, _ = _write_manager()
    schedule = _recovery_draft_schedule()
    result = manager.approve_and_write(
        approval_event_id="does_not_exist",
        draft=schedule,
        target_calendar_id="primary",
    )
    assert result.status is WriteStatus.ABORTED_PRE_WRITE
    assert result.reason_code is ReasonCode.APPROVAL_MISSING
    assert adapter.all_events() == []  # no calendar change without approval


def test_recovery_draft_write_succeeds_with_recorded_approval() -> None:
    from datetime import timedelta

    from agentic_calendar.calendar_writer.manager import WriteStatus
    from agentic_calendar.contracts.approval_event import (
        ApprovalActionType,
        ApprovalEvent,
        HashAlgorithm,
    )
    from agentic_calendar.contracts.hashing import canonical_payload_hash

    manager, adapter, approval_store = _write_manager()
    schedule = _recovery_draft_schedule()
    approval_store.save(
        ApprovalEvent(
            approval_event_id="approval_recovery_1",
            user_id="u1",
            plan_id=schedule.plan_version,
            draft_schedule_id=schedule.draft_schedule_id,
            action_type=ApprovalActionType.ADD_TO_CALENDAR,
            approved_payload_hash=canonical_payload_hash(schedule, "v1"),
            hash_algorithm=HashAlgorithm.SHA256,
            hash_canonicalization_version="v1",
            created_at=TS,
            expires_at=TS + timedelta(hours=24),
        )
    )
    result = manager.approve_and_write(
        approval_event_id="approval_recovery_1",
        draft=schedule,
        target_calendar_id="primary",
    )
    assert result.status is WriteStatus.SUCCESS
    assert len(adapter.all_events()) == len(schedule.entries)
