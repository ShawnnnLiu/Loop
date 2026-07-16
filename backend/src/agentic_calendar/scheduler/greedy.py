"""Pure greedy MVP placement loop.

Algorithm:

1. Filter out tasks whose prerequisites are not met → ``DEPENDENCY_BLOCKED``.
2. Reject tasks where ``estimated_duration_min > max_session_length_min`` and
   ``splittable=False`` → ``TASK_TOO_LONG_UNSPLITTABLE``.
3. For each remaining task in topo + priority order, place it via the
   scored-candidate machinery (``scoring.py``): enumerate feasible
   candidates (deep-work / daily-load / break-between-deep checks), pick
   the ``(cost, start)`` argmin. With the current constant-0 cost this
   selects the first window that fits (axiom 05 "Rollout status").
4. If no candidate is feasible, emit a typed reason with debug payload.
5. After every placement, mark the placed range busy so subsequent tasks see it.

The algorithm is intentionally naïve. Phase 3 may swap in OR-Tools without
changing the public contract (``schedule(input) -> SchedulerOutput``).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime

from agentic_calendar.contracts.common_types import FocusLevel, Priority
from agentic_calendar.contracts.reason_codes import ReasonCode
from agentic_calendar.contracts.scheduler_output import (
    CalendarEventStatus,
    RepairOption,
    ScheduledTask,
    SchedulerOutput,
    ScheduleStatus,
    UnscheduledTask,
)
from agentic_calendar.contracts.task_plan import Task

from . import debug as dbg
from .errors import SchedulerError
from .inputs import FreeBusyInterval, SchedulerInput
from .ordering import topological_order
from .scoring import (
    PlacementState,
    day_key,
    enumerate_candidates,
    select_placement,
)
from .windows import FreeWindow, enumerate_free_windows


def schedule(
    inp: SchedulerInput,
    *,
    module_priority: Mapping[str, Priority] | None = None,
) -> SchedulerOutput:
    """Public entry point. Always returns a ``SchedulerOutput`` (never raises).

    Any internal :class:`SchedulerError` is caught here and translated into a
    schema-valid ``schedule_status="failed"`` output carrying the exception's
    typed ``reason_code`` (axiom 16) — no raw exception leaves the region.
    """
    try:
        return _schedule_validated(inp, module_priority=module_priority)
    except SchedulerError as exc:
        return _scheduler_error_output(inp, exc)


def _scheduler_error_output(
    inp: SchedulerInput, exc: SchedulerError
) -> SchedulerOutput:
    """Translate an internal error into a typed, schema-valid FAILED output.

    Every plan task becomes an ``UnscheduledTask`` carrying the exception's
    ``reason_code`` (``TaskPlan`` guarantees at least one task, so the
    failed-output list invariant always holds).
    """
    unscheduled = [
        UnscheduledTask(
            task_id=task.task_id,
            reason_code=type(exc).reason_code,
            debug=dbg.scheduler_error_debug(
                error_type=type(exc).__name__, detail=str(exc)
            ),
        )
        for task in inp.plan.tasks
    ]
    return SchedulerOutput(
        run_id=inp.run_id,
        plan_version=inp.plan_version,
        schedule_status=ScheduleStatus.FAILED,
        scheduled_tasks=[],
        unscheduled_tasks=unscheduled,
        available_capacity_min=0,
        largest_available_block_min=0,
        repair_options=_repair_options_for(unscheduled, ScheduleStatus.FAILED),
    )


def _schedule_validated(
    inp: SchedulerInput,
    *,
    module_priority: Mapping[str, Priority] | None = None,
) -> SchedulerOutput:
    """Run the greedy placement loop on contract-valid input."""
    ordered_tasks = topological_order(inp.plan, module_priority=module_priority)
    free_windows = enumerate_free_windows(
        horizon_start=inp.horizon_start,
        horizon_end=inp.horizon_end,
        free_busy=list(inp.calendar_free_busy),
        policy=inp.policy,
    )
    available_capacity_min = sum(w.duration_min for w in free_windows)
    largest_block_min = max((w.duration_min for w in free_windows), default=0)

    state = PlacementState(
        busy=list(inp.calendar_free_busy),
        minutes_per_day={},
        last_deep_end={},
    )

    scheduled: list[ScheduledTask] = []
    unscheduled: list[UnscheduledTask] = []
    # Within a single run, a task placed earlier in topo order satisfies the
    # dependency relation for tasks placed later (axiom 11: prereqs are
    # computed deterministically from completion plus in-flight placements).
    #
    # Because ``ordered_tasks`` is a topological order, the only deps a task
    # can have are tasks that appeared earlier in the iteration — so the
    # per-task readiness check is a single subset test against the running
    # ``completed_or_placed`` set: O(deps) per task, O(edges) overall.
    completed_or_placed: set[str] = set(inp.completed_task_ids)

    for task in ordered_tasks:
        blocked_by = [dep for dep in task.dependencies if dep not in completed_or_placed]
        if blocked_by:
            unscheduled.append(
                UnscheduledTask(
                    task_id=task.task_id,
                    reason_code=ReasonCode.DEPENDENCY_BLOCKED,
                    debug=dbg.dependency_blocked_debug(blocked_by=blocked_by),
                )
            )
            continue

        if (
            task.estimated_duration_min > inp.policy.max_session_length_min
            and not task.splittable
        ):
            unscheduled.append(
                UnscheduledTask(
                    task_id=task.task_id,
                    reason_code=ReasonCode.TASK_TOO_LONG_UNSPLITTABLE,
                    debug=dbg.task_too_long_unsplittable_debug(
                        duration_min=task.estimated_duration_min,
                        max_session_length_min=inp.policy.max_session_length_min,
                    ),
                )
            )
            continue

        placement = _try_place(task, free_windows, inp, state)
        if placement is None:
            unscheduled.append(_failure_for(task, free_windows, inp))
            continue

        scheduled.append(
            ScheduledTask(
                task_id=task.task_id,
                start=placement.start,
                end=placement.end,
                calendar_event_status=CalendarEventStatus.DRAFT_ONLY,
            )
        )
        _record_placement(task, placement, state, free_windows, inp)
        completed_or_placed.add(task.task_id)

    unscheduled = _promote_capacity_failures(
        unscheduled,
        ordered_tasks=ordered_tasks,
        available_capacity_min=available_capacity_min,
    )

    status = _status_for(scheduled, unscheduled)
    repair_options = _repair_options_for(unscheduled, status)

    return SchedulerOutput(
        run_id=inp.run_id,
        plan_version=inp.plan_version,
        schedule_status=status,
        scheduled_tasks=scheduled,
        unscheduled_tasks=unscheduled,
        available_capacity_min=available_capacity_min,
        largest_available_block_min=largest_block_min,
        repair_options=repair_options,
    )


def _promote_capacity_failures(
    unscheduled: list[UnscheduledTask],
    *,
    ordered_tasks: list[Task],
    available_capacity_min: int,
) -> list[UnscheduledTask]:
    """Promote per-task ``NO_VALID_CONTIGUOUS_BLOCK`` to a global capacity failure.

    Axiom 05: when total required time exceeds available capacity, the cause
    is capacity (or timeline) — not calendar fragmentation. Emitting
    ``INSUFFICIENT_WEEKLY_CAPACITY`` on every fragmentation failure in that
    case lets the supervisor and approval UI propose ``EXTEND_TIMELINE`` /
    ``REDUCE_SCOPE`` instead of useless ``SPLIT_TASK`` repairs.
    """
    total_required_min = sum(t.estimated_duration_min for t in ordered_tasks)
    if total_required_min <= available_capacity_min:
        return unscheduled
    promoted: list[UnscheduledTask] = []
    for u in unscheduled:
        if u.reason_code is ReasonCode.NO_VALID_CONTIGUOUS_BLOCK:
            promoted.append(
                UnscheduledTask(
                    task_id=u.task_id,
                    reason_code=ReasonCode.INSUFFICIENT_WEEKLY_CAPACITY,
                    debug=dbg.insufficient_weekly_capacity_debug(
                        total_required_min=total_required_min,
                        available_capacity_min=available_capacity_min,
                    ),
                )
            )
        else:
            promoted.append(u)
    return promoted


@dataclass(frozen=True, slots=True)
class _Placement:
    start: datetime
    end: datetime
    window_was_deep: bool


def _try_place(
    task: Task,
    windows: list[FreeWindow],
    inp: SchedulerInput,
    state: PlacementState,
) -> _Placement | None:
    """Select a placement via the scored-candidate machinery (axiom 05)."""
    candidates = enumerate_candidates(task, windows, state, inp.policy)
    chosen = select_placement(candidates)
    if chosen is None:
        return None
    return _Placement(
        start=chosen.start, end=chosen.end, window_was_deep=chosen.window.is_deep_work
    )


def _record_placement(
    task: Task,
    placement: _Placement,
    state: PlacementState,
    windows: list[FreeWindow],
    inp: SchedulerInput,
) -> None:
    state.busy.append(FreeBusyInterval(start=placement.start, end=placement.end))
    state.busy.sort(key=lambda i: i.start)
    key = day_key(placement.start)
    state.minutes_per_day[key] = (
        state.minutes_per_day.get(key, 0) + task.estimated_duration_min
    )
    if task.required_focus_level is FocusLevel.DEEP:
        state.last_deep_end[key] = placement.end
    # Re-enumerate after busy list update
    fresh = enumerate_free_windows(
        horizon_start=inp.horizon_start,
        horizon_end=inp.horizon_end,
        free_busy=state.busy,
        policy=inp.policy,
    )
    windows.clear()
    windows.extend(fresh)


def _failure_for(
    task: Task,
    windows: list[FreeWindow],
    inp: SchedulerInput,
) -> UnscheduledTask:
    """Build the right typed failure for a task that nothing accepted."""
    needs_deep = task.required_focus_level is FocusLevel.DEEP
    largest = max((w.duration_min for w in windows), default=0)
    deep_window_count = sum(1 for w in windows if w.is_deep_work)

    if needs_deep and deep_window_count == 0 and inp.policy.respect_deep_work_windows:
        return UnscheduledTask(
            task_id=task.task_id,
            reason_code=ReasonCode.DEEP_WORK_REQUIRED_UNAVAILABLE,
            debug=dbg.deep_work_required_unavailable_debug(
                required_duration_min=task.estimated_duration_min,
                deep_work_windows_seen=deep_window_count,
            ),
        )

    rejected = [
        dbg.rejected_window(
            start=w.start,
            duration_min=w.duration_min,
            rejection_reason=_rejection_reason(w, task, inp),
        )
        for w in windows
    ]
    suggested = (
        RepairOption.SPLIT_TASK
        if task.splittable and task.estimated_duration_min > largest
        else None
    )
    return UnscheduledTask(
        task_id=task.task_id,
        reason_code=ReasonCode.NO_VALID_CONTIGUOUS_BLOCK,
        debug=dbg.no_valid_contiguous_block_debug(
            required_duration_min=task.estimated_duration_min,
            largest_available_block_min=largest,
            required_focus_level=task.required_focus_level.value,
            rejected_windows=rejected,
            suggested_repair=suggested,
        ),
    )


def _rejection_reason(window: FreeWindow, task: Task, inp: SchedulerInput) -> str:
    if window.duration_min < task.estimated_duration_min:
        return "too_short"
    if (
        task.required_focus_level is FocusLevel.DEEP
        and inp.policy.respect_deep_work_windows
        and not window.is_deep_work
    ):
        return "not_deep_work_window"
    if window.end.time() > _to_time(inp.policy.no_events_after):
        return "ends_after_user_limit"
    return "constraint_unmet"


def _to_time(hhmm: str):  # type: ignore[no-untyped-def]
    from datetime import time

    hh, mm = hhmm.split(":")
    return time(int(hh), int(mm))


def _status_for(
    scheduled: list[ScheduledTask], unscheduled: list[UnscheduledTask]
) -> ScheduleStatus:
    if not unscheduled:
        return ScheduleStatus.SUCCESS
    if not scheduled:
        return ScheduleStatus.FAILED
    return ScheduleStatus.PARTIAL_FAILURE


def _repair_options_for(
    unscheduled: list[UnscheduledTask], status: ScheduleStatus
) -> list[RepairOption]:
    """Always include the canonical option list (axiom 05) on non-success."""
    if status is ScheduleStatus.SUCCESS:
        return []
    return [
        RepairOption.SPLIT_LARGE_TASKS,
        RepairOption.EXTEND_TIMELINE,
        RepairOption.REDUCE_SCOPE,
        RepairOption.INCREASE_WEEKLY_HOURS,
    ]
