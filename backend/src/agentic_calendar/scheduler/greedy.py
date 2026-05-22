"""Pure greedy MVP placement loop.

Algorithm:

1. Filter out tasks whose prerequisites are not met → ``DEPENDENCY_BLOCKED``.
2. Reject tasks where ``estimated_duration_min > max_session_length_min`` and
   ``splittable=False`` → ``TASK_TOO_LONG_UNSPLITTABLE``.
3. For each remaining task in topo + priority order, find the first window
   that fits (with deep-work / daily-load / break-between-deep checks).
4. If no window fits, emit a typed reason with debug payload.
5. After every placement, mark the placed range busy so subsequent tasks see it.

The algorithm is intentionally naïve. Phase 3 may swap in OR-Tools without
changing the public contract (``schedule(input) -> SchedulerOutput``).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta

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
from .inputs import FreeBusyInterval, SchedulerInput
from .ordering import topological_order
from .windows import FreeWindow, enumerate_free_windows


@dataclass(slots=True)
class _PlacementState:
    """Mutable state threaded through the placement loop."""

    busy: list[FreeBusyInterval]
    minutes_per_day: dict[str, int]
    last_deep_end: dict[str, datetime]


def schedule(
    inp: SchedulerInput,
    *,
    module_priority: Mapping[str, Priority] | None = None,
) -> SchedulerOutput:
    """Public entry point. Always returns a ``SchedulerOutput`` (never raises)."""
    ordered_tasks = topological_order(inp.plan, module_priority=module_priority)
    free_windows = enumerate_free_windows(
        horizon_start=inp.horizon_start,
        horizon_end=inp.horizon_end,
        free_busy=list(inp.calendar_free_busy),
        policy=inp.policy,
    )
    available_capacity_min = sum(w.duration_min for w in free_windows)
    largest_block_min = max((w.duration_min for w in free_windows), default=0)

    state = _PlacementState(
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
    state: _PlacementState,
) -> _Placement | None:
    """Return the first window-aligned placement that satisfies all constraints."""
    needs_deep = task.required_focus_level is FocusLevel.DEEP
    duration = task.estimated_duration_min
    for window in _live_windows(windows, state.busy):
        if window.duration_min < duration:
            continue
        if needs_deep and inp.policy.respect_deep_work_windows and not window.is_deep_work:
            continue
        candidate_start = window.start
        candidate_end = candidate_start + timedelta(minutes=duration)
        if candidate_end > window.end:
            continue
        day_key = _day_key(candidate_start)
        used_today = state.minutes_per_day.get(day_key, 0)
        if used_today + duration > inp.policy.max_daily_study_min:
            continue
        if needs_deep:
            last = state.last_deep_end.get(day_key)
            if last is not None:
                gap = (candidate_start - last).total_seconds() / 60
                if gap < inp.policy.min_break_between_deep_blocks_min:
                    continue
        return _Placement(
            start=candidate_start, end=candidate_end, window_was_deep=window.is_deep_work
        )
    return None


def _record_placement(
    task: Task,
    placement: _Placement,
    state: _PlacementState,
    windows: list[FreeWindow],
    inp: SchedulerInput,
) -> None:
    state.busy.append(FreeBusyInterval(start=placement.start, end=placement.end))
    state.busy.sort(key=lambda i: i.start)
    day_key = _day_key(placement.start)
    state.minutes_per_day[day_key] = (
        state.minutes_per_day.get(day_key, 0) + task.estimated_duration_min
    )
    if task.required_focus_level is FocusLevel.DEEP:
        state.last_deep_end[day_key] = placement.end
    # Re-enumerate after busy list update
    fresh = enumerate_free_windows(
        horizon_start=inp.horizon_start,
        horizon_end=inp.horizon_end,
        free_busy=state.busy,
        policy=inp.policy,
    )
    windows.clear()
    windows.extend(fresh)


def _live_windows(
    windows: list[FreeWindow], busy: list[FreeBusyInterval]
) -> list[FreeWindow]:
    """Return windows untouched by ``busy`` (defensive — windows are recomputed)."""
    if not busy:
        return windows
    live: list[FreeWindow] = []
    for w in windows:
        overlaps = any(b.start < w.end and b.end > w.start for b in busy)
        if not overlaps:
            live.append(w)
    return live


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


def _day_key(dt: datetime) -> str:
    return dt.date().isoformat()


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
