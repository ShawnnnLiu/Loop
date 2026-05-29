"""Golden scenarios that exercise the Scheduler end-to-end.

Covers ``docs/golden-test-cases.md``:

* Scenario 1:  Limited weekly capacity
* Scenario 2:  No weekday availability
* Scenario 5:  Task too long, unsplittable
* Scenario 6:  Calendar full except short gaps (NO_VALID_CONTIGUOUS_BLOCK)
* Scenario 12: Timeline infeasibility (INSUFFICIENT_WEEKLY_CAPACITY)
* Scenario 15: Capacity but no contiguous block

Every scenario asserts:

* the typed ``ReasonCode`` on the unscheduled task,
* the structured ``debug`` payload,
* the Supervisor's next state from the deterministic transition table,
* the no-calendar-write invariant (``CalendarEventStatus.DRAFT_ONLY`` only).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from agentic_calendar.contracts.reason_codes import ReasonCode
from agentic_calendar.contracts.scheduler_output import (
    RepairOption,
    ScheduleStatus,
)
from agentic_calendar.contracts.task_plan import TaskPlan
from agentic_calendar.scheduler import schedule
from agentic_calendar.scheduler.inputs import FreeBusyInterval, SchedulerInput
from agentic_calendar.scheduler.policy import (
    DeepWorkWindowPolicy,
    SchedulingPolicy,
)
from agentic_calendar.supervisor import (
    SupervisorSignal,
    SupervisorState,
    route,
)
from tests.golden.conftest import (
    HORIZON_START,
    assert_no_calendar_write_leaks,
    make_task,
)


def _signal_for(status: ScheduleStatus) -> SupervisorSignal:
    if status is ScheduleStatus.SUCCESS:
        return SupervisorSignal.SCHEDULER_SUCCESS
    if status is ScheduleStatus.PARTIAL_FAILURE:
        return SupervisorSignal.SCHEDULER_PARTIAL_FAILURE
    return SupervisorSignal.SCHEDULER_FULL_FAILURE


def _input(
    *, plan: TaskPlan, policy: SchedulingPolicy,
    free_busy: list[FreeBusyInterval] | None = None,
    horizon_days: int = 7,
    horizon_start: datetime = HORIZON_START,
    run_id: str = "run_golden",
) -> SchedulerInput:
    return SchedulerInput(
        run_id=run_id,
        plan_version=plan.plan_version,
        plan=plan,
        policy=policy,
        calendar_free_busy=free_busy or [],
        horizon_start=horizon_start,
        horizon_end=horizon_start + timedelta(days=horizon_days),
    )


# --------------------------------------------------------------------------- #
# Scenario 1 — Limited weekly capacity
# --------------------------------------------------------------------------- #

def test_scenario_1_limited_weekly_capacity_emits_insufficient_capacity(
    relaxed_policy,  # type: ignore[no-untyped-def]
) -> None:
    """User has ~3 free hours but the plan needs 8."""
    plan = TaskPlan.model_validate({
        "plan_version": "p_capacity",
        "tasks": [
            make_task(task_id=f"t{i}", estimated_duration_min=120, splittable=True)
            for i in range(4)  # 4 * 120 = 480 min required
        ],
    })
    capped_policy = relaxed_policy.model_copy(
        update={"no_events_before": "20:00", "no_events_after": "21:00"}
    )

    out = schedule(_input(plan=plan, policy=capped_policy, horizon_days=3))

    assert out.schedule_status in (ScheduleStatus.FAILED, ScheduleStatus.PARTIAL_FAILURE)
    assert out.available_capacity_min < sum(
        t.estimated_duration_min for t in plan.tasks
    )
    capacity_failures = [
        u for u in out.unscheduled_tasks
        if u.reason_code is ReasonCode.INSUFFICIENT_WEEKLY_CAPACITY
    ]
    assert capacity_failures, "expected at least one INSUFFICIENT_WEEKLY_CAPACITY"
    sample = capacity_failures[0]
    assert sample.debug["shortfall_min"] > 0
    assert sample.debug["suggested_repair"] == RepairOption.EXTEND_TIMELINE.value

    assert RepairOption.EXTEND_TIMELINE in out.repair_options
    assert RepairOption.REDUCE_SCOPE in out.repair_options

    assert (
        route(SupervisorState.SCHEDULER_RUNNING, _signal_for(out.schedule_status))
        is SupervisorState.PLANNER_RUNNING
    )
    assert_no_calendar_write_leaks(out)


# --------------------------------------------------------------------------- #
# Scenario 2 — No weekday availability
# --------------------------------------------------------------------------- #

def test_scenario_2_no_weekday_availability_schedules_on_weekend_only() -> None:
    """Block out every weekday window so only the weekend is available."""
    weekend_friendly = SchedulingPolicy(
        no_events_before="08:00",
        no_events_after="22:30",
        allow_weekends=True,
        min_break_between_deep_blocks_min=30,
        max_daily_study_min=240,
        respect_deep_work_windows=True,
        deep_work_windows=[
            DeepWorkWindowPolicy(day="Sat", start="09:00", end="13:00"),
        ],
        max_session_length_min=120,
    )
    plan = TaskPlan.model_validate({
        "plan_version": "p_weekend",
        "tasks": [
            make_task(
                task_id="deep_one",
                estimated_duration_min=90,
                required_focus_level="deep",
            ),
        ],
    })
    horizon_start = datetime(2026, 5, 4, 0, 0, 0, tzinfo=UTC)  # Mon
    weekday_busy = [
        FreeBusyInterval(
            start=horizon_start + timedelta(days=d, hours=8),
            end=horizon_start + timedelta(days=d, hours=22, minutes=30),
        )
        for d in range(5)  # Mon-Fri fully busy
    ]

    out = schedule(
        _input(
            plan=plan,
            policy=weekend_friendly,
            free_busy=weekday_busy,
            horizon_days=7,
            horizon_start=horizon_start,
        )
    )
    assert out.schedule_status is ScheduleStatus.SUCCESS
    placement = out.scheduled_tasks[0]
    assert placement.start.weekday() == 5  # Saturday
    assert placement.start.time().hour >= 9
    assert (
        route(SupervisorState.SCHEDULER_RUNNING, _signal_for(out.schedule_status))
        is SupervisorState.AWAITING_USER_APPROVAL
    )
    assert_no_calendar_write_leaks(out)


# --------------------------------------------------------------------------- #
# Scenario 5 — Task too long, unsplittable
# --------------------------------------------------------------------------- #

def test_scenario_5_task_too_long_unsplittable(relaxed_policy) -> None:  # type: ignore[no-untyped-def]
    plan = TaskPlan.model_validate({
        "plan_version": "p_too_long",
        "tasks": [
            make_task(
                task_id="huge",
                estimated_duration_min=relaxed_policy.max_session_length_min + 30,
                splittable=False,
            ),
        ],
    })
    out = schedule(_input(plan=plan, policy=relaxed_policy, horizon_days=2))

    assert out.schedule_status is ScheduleStatus.FAILED
    u = out.unscheduled_tasks[0]
    assert u.reason_code is ReasonCode.TASK_TOO_LONG_UNSPLITTABLE
    assert u.debug["suggested_repair"] == RepairOption.ASK_USER.value
    assert u.debug["max_session_length_min"] == relaxed_policy.max_session_length_min
    assert (
        route(SupervisorState.SCHEDULER_RUNNING, _signal_for(out.schedule_status))
        is SupervisorState.PLANNER_RUNNING
    )
    assert_no_calendar_write_leaks(out)


# --------------------------------------------------------------------------- #
# Scenario 6 / 15 — Calendar full except short gaps + capacity-but-no-block
# --------------------------------------------------------------------------- #

def test_scenario_6_and_15_capacity_but_no_contiguous_block(
    relaxed_policy,  # type: ignore[no-untyped-def]
) -> None:
    """Two 60-min windows = 120 min capacity, but task needs 90 min contiguously."""
    plan = TaskPlan.model_validate({
        "plan_version": "p_fragmented",
        "tasks": [
            make_task(task_id="x", estimated_duration_min=90, splittable=True),
        ],
    })
    short_window_only = relaxed_policy.model_copy(
        update={"no_events_before": "20:00", "no_events_after": "21:00"}
    )

    out = schedule(_input(plan=plan, policy=short_window_only, horizon_days=2))

    assert out.schedule_status is ScheduleStatus.FAILED
    u = out.unscheduled_tasks[0]
    assert u.reason_code is ReasonCode.NO_VALID_CONTIGUOUS_BLOCK
    assert u.debug["required_duration_min"] == 90
    assert u.debug["largest_available_block_min"] == 60
    assert u.debug["suggested_repair"] == RepairOption.SPLIT_TASK.value
    assert (
        route(SupervisorState.SCHEDULER_RUNNING, _signal_for(out.schedule_status))
        is SupervisorState.PLANNER_RUNNING
    )
    assert_no_calendar_write_leaks(out)


# --------------------------------------------------------------------------- #
# Scenario 12 — Timeline infeasibility
# --------------------------------------------------------------------------- #

def test_scenario_12_timeline_infeasibility(relaxed_policy) -> None:  # type: ignore[no-untyped-def]
    """Required minutes far exceed any 1-day horizon → INSUFFICIENT_WEEKLY_CAPACITY."""
    plan = TaskPlan.model_validate({
        "plan_version": "p_timeline",
        "tasks": [
            make_task(task_id=f"t{i}", estimated_duration_min=60, splittable=True)
            for i in range(20)  # 1200 min required
        ],
    })
    out = schedule(_input(plan=plan, policy=relaxed_policy, horizon_days=1))

    assert out.schedule_status is ScheduleStatus.PARTIAL_FAILURE
    capacity_failures = [
        u for u in out.unscheduled_tasks
        if u.reason_code is ReasonCode.INSUFFICIENT_WEEKLY_CAPACITY
    ]
    assert capacity_failures, "expected at least one INSUFFICIENT_WEEKLY_CAPACITY"
    assert RepairOption.EXTEND_TIMELINE in out.repair_options
    assert RepairOption.REDUCE_SCOPE in out.repair_options
    assert (
        route(SupervisorState.SCHEDULER_RUNNING, _signal_for(out.schedule_status))
        is SupervisorState.PLANNER_RUNNING
    )
    assert_no_calendar_write_leaks(out)


# --------------------------------------------------------------------------- #
# Cross-cutting: success path lands in approval, never in writing
# --------------------------------------------------------------------------- #

def test_success_routes_to_awaiting_user_approval_not_calendar(
    relaxed_policy,  # type: ignore[no-untyped-def]
) -> None:
    """Scheduler success must land in approval, never directly in any calendar-write state."""
    plan = TaskPlan.model_validate({
        "plan_version": "p_ok",
        "tasks": [make_task(task_id="t1", estimated_duration_min=60)],
    })
    out = schedule(_input(plan=plan, policy=relaxed_policy))
    assert out.schedule_status is ScheduleStatus.SUCCESS
    next_state = route(
        SupervisorState.SCHEDULER_RUNNING, _signal_for(out.schedule_status)
    )
    assert next_state is SupervisorState.AWAITING_USER_APPROVAL
    assert next_state is not SupervisorState.CALENDAR_WRITE_APPROVED
    assert next_state is not SupervisorState.CALENDAR_WRITE_IN_PROGRESS
    assert_no_calendar_write_leaks(out)
