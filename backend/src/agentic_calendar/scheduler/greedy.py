"""Pure greedy MVP placement loop.

Algorithm (axiom 05 "Scored Placement" + "Insertion order"):

1. Compute the deterministic topological order (module priority /
   cognitive load / task_id tie-breaks) — it remains the *output*
   ordering for scheduled and unscheduled tasks alike.
2. Maintain the ready set: tasks whose dependencies are completed or
   already placed this run. Each round, rank every ready task's feasible
   candidates (window starts plus the intra-window grid, under the
   deep-work / daily-load / break-between-deep hard checks) by the
   integer cost terms, and place the task with the most to lose:
   single-candidate tasks first, then largest regret (second-best -
   best cost), ties by the ordering sort key. Ready tasks that are too
   long and unsplittable (``TASK_TOO_LONG_UNSPLITTABLE``) or have zero
   feasible candidates fail that round with their typed reason.
3. After every placement the placed range becomes busy, windows are
   re-enumerated, and the next round re-ranks against the new state.
4. Tasks whose dependencies never place fail ``DEPENDENCY_BLOCKED``.
5. A bounded polish pass (axiom 05 "Bounded polish pass", ``polish.py``)
   then relocates placed blocks under the schedule-level objective — moves
   only; the failure surface is untouchable by construction.

The algorithm is intentionally a greedy heuristic. Phase 3 may swap in
OR-Tools without changing the public contract
(``schedule(input) -> SchedulerOutput``).
"""

from __future__ import annotations

from collections.abc import Mapping

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
from .ordering import sort_key, topological_order
from .polish import polish_placements
from .scoring import (
    DEFAULT_PLACEMENT_SCORING_CONFIG,
    PlacedBlock,
    PlacementCandidate,
    PlacementRanking,
    PlacementScoringConfig,
    PlacementState,
    compute_day_quotas,
    day_key,
    enumerate_candidates,
    rank_placement,
)
from .windows import FreeWindow, enumerate_free_windows


def schedule(
    inp: SchedulerInput,
    *,
    module_priority: Mapping[str, Priority] | None = None,
    scoring: PlacementScoringConfig | None = None,
) -> SchedulerOutput:
    """Public entry point. Always returns a ``SchedulerOutput`` (never raises).

    ``scoring`` carries the operator-tunable placement weights and knobs
    (``None`` means the journaled defaults) — a keyword-only argument like
    ``module_priority`` so ``SchedulingPolicy`` stays a pure mirror of the
    user profile.

    Any internal :class:`SchedulerError` is caught here and translated into a
    schema-valid ``schedule_status="failed"`` output carrying the exception's
    typed ``reason_code`` (axiom 16) — no raw exception leaves the region.
    """
    try:
        return _schedule_validated(
            inp,
            module_priority=module_priority,
            scoring=scoring if scoring is not None else DEFAULT_PLACEMENT_SCORING_CONFIG,
        )
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
    scoring: PlacementScoringConfig,
) -> SchedulerOutput:
    """Run the greedy placement loop on contract-valid input."""
    ordered_tasks = topological_order(inp.plan, module_priority=module_priority)
    topo_position = {t.task_id: i for i, t in enumerate(ordered_tasks)}
    free_windows = enumerate_free_windows(
        horizon_start=inp.horizon_start,
        horizon_end=inp.horizon_end,
        free_busy=list(inp.calendar_free_busy),
        policy=inp.policy,
    )
    available_capacity_min = sum(w.duration_min for w in free_windows)
    largest_block_min = max((w.duration_min for w in free_windows), default=0)
    day_quotas = compute_day_quotas(inp, free_windows)

    state = PlacementState(
        busy=list(inp.calendar_free_busy),
        minutes_per_day={},
        last_deep_end={},
        placed=[],
    )

    scheduled: list[ScheduledTask] = []
    unscheduled: list[UnscheduledTask] = []
    # Within a single run, a placed task satisfies the dependency relation
    # for tasks ranked later (axiom 11: prereqs are computed
    # deterministically from completion plus in-flight placements). A task
    # enters the ready set only when every dependency is in this set, so
    # topology stays a hard gate no matter which ready task wins a round.
    completed_or_placed: set[str] = set(inp.completed_task_ids)

    remaining = list(ordered_tasks)
    while remaining:
        ready = [
            t
            for t in remaining
            if all(dep in completed_or_placed for dep in t.dependencies)
        ]
        if not ready:
            break
        ready.sort(key=lambda t: sort_key(t, module_priority))
        resolved: set[str] = set()
        ranked: list[tuple[Task, PlacementRanking]] = []
        for task in ready:
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
                resolved.add(task.task_id)
                continue
            candidates = enumerate_candidates(
                task, free_windows, state, inp.policy, scoring
            )
            ranking = rank_placement(
                candidates,
                task=task,
                state=state,
                policy=inp.policy,
                scoring=scoring,
                day_quotas=day_quotas,
                horizon_start=inp.horizon_start,
            )
            if ranking is None:
                # Fail-fast: a ready task with zero candidates fails this
                # round (axiom 05 "Insertion order") — its dependents never
                # become ready and fall out as DEPENDENCY_BLOCKED below.
                unscheduled.append(_failure_for(task, free_windows, inp))
                resolved.add(task.task_id)
                continue
            ranked.append((task, ranking))

        if ranked:
            task, ranking = min(
                ranked,
                key=lambda pair: (
                    0 if pair[1].single_candidate else 1,
                    -pair[1].regret,
                    sort_key(pair[0], module_priority),
                ),
            )
            chosen = ranking.candidate
            scheduled.append(
                ScheduledTask(
                    task_id=task.task_id,
                    start=chosen.start,
                    end=chosen.end,
                    calendar_event_status=CalendarEventStatus.DRAFT_ONLY,
                )
            )
            _record_placement(task, chosen, state, free_windows, inp)
            completed_or_placed.add(task.task_id)
            resolved.add(task.task_id)

        remaining = [t for t in remaining if t.task_id not in resolved]

    for task in remaining:  # never became ready — a dependency failed upstream
        unscheduled.append(
            UnscheduledTask(
                task_id=task.task_id,
                reason_code=ReasonCode.DEPENDENCY_BLOCKED,
                debug=dbg.dependency_blocked_debug(
                    blocked_by=[
                        dep
                        for dep in task.dependencies
                        if dep not in completed_or_placed
                    ]
                ),
            )
        )

    # Output ordering is the task's topological position, not placement
    # round (axiom 05 "Insertion order") — byte-identical to the linear
    # loop whenever placements coincide.
    scheduled.sort(key=lambda st: topo_position[st.task_id])
    unscheduled.sort(key=lambda u: topo_position[u.task_id])

    # Bounded polish (axiom 05): moves placed blocks only, so unscheduled
    # tasks — and therefore reason codes and debug payloads — are untouched.
    scheduled = polish_placements(scheduled, inp, scoring)

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


def _record_placement(
    task: Task,
    placement: PlacementCandidate,
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
    is_deep = task.required_focus_level is FocusLevel.DEEP
    if is_deep:
        state.last_deep_end[key] = placement.end
    state.placed.append(
        PlacedBlock(start=placement.start, end=placement.end, is_deep=is_deep)
    )
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
