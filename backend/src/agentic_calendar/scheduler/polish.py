"""Bounded polish pass (axiom 05 "Bounded polish pass").

A deterministic local search that runs after the greedy placement loop and
before the capacity-vs-fragmentation promotion. Greedy-with-scoring places
each task against the state of its own round, so early placements can turn
suboptimal once later blocks land; this pass relocates placed blocks to
strictly lower the **schedule-level** total cost — the ``score_blocks``
totals shared with ``score_schedule``, never a sum of the path-dependent
per-placement marginals.

Bounds and determinism: at most :data:`POLISH_SWEEPS` sweeps; each sweep
snapshots the placed blocks in ``(start, task_id)`` order and applies per
block at most the single best strictly-improving move under the key
``(total_after, new_start)``. Strict integer improvement plus the fixed
sweep count and scan order make the pass terminating, reproducible, and
idempotent at its fixed point.

The pass **moves** blocks only. It never unschedules a task, never
reschedules a failed one, and never touches ``unscheduled_tasks`` — reason
codes and debug payloads are untouchable by construction.
"""

from __future__ import annotations

import itertools
from collections.abc import Callable
from datetime import datetime

from agentic_calendar.contracts.common_types import FocusLevel
from agentic_calendar.contracts.scheduler_output import (
    CalendarEventStatus,
    ScheduledTask,
)
from agentic_calendar.contracts.task_plan import Task

from .inputs import FreeBusyInterval, SchedulerInput
from .policy import SchedulingPolicy
from .scoring import (
    PlacedBlock,
    PlacementCandidate,
    PlacementScoringConfig,
    PlacementState,
    compute_day_quotas,
    day_key,
    enumerate_candidates,
    score_blocks,
)
from .windows import enumerate_free_windows

#: Axiom 05: the polish pass is bounded by construction — two sweeps, fixed
#: scan order, strict improvement. Not a tuning knob.
POLISH_SWEEPS = 2

_Span = tuple[datetime, datetime]


def polish_placements(
    scheduled: list[ScheduledTask],
    inp: SchedulerInput,
    scoring: PlacementScoringConfig,
) -> list[ScheduledTask]:
    """Return ``scheduled`` with strictly-improving relocations applied.

    Output preserves the input list's ordering and length: entry *i* is the
    same task as input entry *i*, moved iff a feasible relocation strictly
    lowered the schedule-level total cost. Unmoved entries are returned as
    the same objects.
    """
    if not scheduled:
        return list(scheduled)

    tasks_by_id = {t.task_id: t for t in inp.plan.tasks}
    dependents: dict[str, list[str]] = {}
    for task in inp.plan.tasks:
        for dep in task.dependencies:
            dependents.setdefault(dep, []).append(task.task_id)

    positions: dict[str, _Span] = {
        st.task_id: (st.start, st.end) for st in scheduled
    }
    # Input-only derivations, paid once for every hypothetical evaluation.
    initial_windows = enumerate_free_windows(
        horizon_start=inp.horizon_start,
        horizon_end=inp.horizon_end,
        free_busy=list(inp.calendar_free_busy),
        policy=inp.policy,
    )
    day_quotas = compute_day_quotas(inp, initial_windows)

    def total_for(pos: dict[str, _Span]) -> int:
        blocks = [
            PlacedBlock(
                start=start,
                end=end,
                is_deep=(
                    tasks_by_id[task_id].required_focus_level is FocusLevel.DEEP
                ),
            )
            for task_id, (start, end) in pos.items()
        ]
        return score_blocks(
            blocks,
            inp,
            scoring,
            initial_windows=initial_windows,
            day_quotas=day_quotas,
        ).total_cost

    current_total = total_for(positions)
    for _ in range(POLISH_SWEEPS):
        moved = False
        snapshot = sorted(positions, key=lambda tid: (positions[tid][0], tid))
        for task_id in snapshot:
            best = _best_relocation(
                tasks_by_id[task_id],
                positions=positions,
                current_total=current_total,
                total_for=total_for,
                dependents=dependents,
                tasks_by_id=tasks_by_id,
                inp=inp,
                scoring=scoring,
            )
            if best is None:
                continue
            new_total, span = best
            positions[task_id] = span
            current_total = new_total
            moved = True
        if not moved:
            break

    return [
        st
        if positions[st.task_id] == (st.start, st.end)
        else ScheduledTask(
            task_id=st.task_id,
            start=positions[st.task_id][0],
            end=positions[st.task_id][1],
            calendar_event_status=CalendarEventStatus.DRAFT_ONLY,
        )
        for st in scheduled
    ]


def _best_relocation(
    task: Task,
    *,
    positions: dict[str, _Span],
    current_total: int,
    total_for: Callable[[dict[str, _Span]], int],
    dependents: dict[str, list[str]],
    tasks_by_id: dict[str, Task],
    inp: SchedulerInput,
    scoring: PlacementScoringConfig,
) -> tuple[int, _Span] | None:
    """The single best strictly-improving feasible move for one block.

    Returns ``(total_after, (start, end))`` minimizing ``(total_after,
    start)``, or ``None`` when no feasible relocation strictly improves the
    schedule-level total.
    """
    current_span = positions[task.task_id]
    others = {tid: span for tid, span in positions.items() if tid != task.task_id}

    # The five hard checks with the block's own occupancy removed: rebuild
    # busy / daily minutes / placed blocks from every *other* placement,
    # re-enumerate windows, and reuse the loop's candidate machinery. The
    # deep-gap check is done pairwise below (both neighbors — the greedy
    # append-only loop only ever checked the previous one), so the state
    # carries no ``last_deep_end``.
    other_busy = sorted(
        [*inp.calendar_free_busy]
        + [FreeBusyInterval(start=s, end=e) for (s, e) in others.values()],
        key=lambda i: i.start,
    )
    windows = enumerate_free_windows(
        horizon_start=inp.horizon_start,
        horizon_end=inp.horizon_end,
        free_busy=other_busy,
        policy=inp.policy,
    )
    minutes_per_day: dict[str, int] = {}
    other_blocks: list[PlacedBlock] = []
    for tid, (start, end) in others.items():
        key = day_key(start)
        minutes_per_day[key] = (
            minutes_per_day.get(key, 0) + tasks_by_id[tid].estimated_duration_min
        )
        other_blocks.append(
            PlacedBlock(
                start=start,
                end=end,
                is_deep=tasks_by_id[tid].required_focus_level is FocusLevel.DEEP,
            )
        )
    state = PlacementState(
        busy=other_busy,
        minutes_per_day=minutes_per_day,
        last_deep_end={},
        placed=other_blocks,
    )
    candidates = enumerate_candidates(task, windows, state, inp.policy, scoring)

    # Dependency order both directions, among placed blocks (axiom 05).
    dep_floor = max(
        (others[dep][1] for dep in task.dependencies if dep in others),
        default=None,
    )
    children = dependents.get(task.task_id, [])
    dep_ceiling = min(
        (others[child][0] for child in children if child in others),
        default=None,
    )

    is_deep = task.required_focus_level is FocusLevel.DEEP
    best: tuple[int, _Span] | None = None
    for candidate in candidates:
        span = (candidate.start, candidate.end)
        if span == current_span:
            continue  # staying put is not a move
        if dep_floor is not None and candidate.start < dep_floor:
            continue
        if dep_ceiling is not None and candidate.end > dep_ceiling:
            continue
        if is_deep and not _deep_gaps_ok(candidate, other_blocks, inp.policy):
            continue
        total_after = total_for({**others, task.task_id: span})
        if total_after >= current_total:
            continue
        if best is None or (total_after, candidate.start) < (best[0], best[1][0]):
            best = (total_after, span)
    return best


def _deep_gaps_ok(
    candidate: PlacementCandidate,
    other_blocks: list[PlacedBlock],
    policy: SchedulingPolicy,
) -> bool:
    """Pairwise same-day deep-gap check after a hypothetical deep move.

    Every consecutive pair of same-day deep blocks — the moved block among
    them — must keep a gap of at least
    ``policy.min_break_between_deep_blocks_min``, checked against **both**
    neighbors.
    """
    key = day_key(candidate.start)
    day_deep = sorted(
        [b for b in other_blocks if b.is_deep and day_key(b.start) == key]
        + [PlacedBlock(start=candidate.start, end=candidate.end, is_deep=True)],
        key=lambda b: b.start,
    )
    required = policy.min_break_between_deep_blocks_min
    for earlier, later in itertools.pairwise(day_deep):
        gap_min = int((later.start - earlier.end).total_seconds() // 60)
        if gap_min < required:
            return False
    return True
