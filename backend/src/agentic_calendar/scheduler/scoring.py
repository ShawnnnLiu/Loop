"""Placement-candidate machinery for the greedy scheduler.

Axiom 05 "Scored Placement": enumerate every feasible candidate start, then
pick the deterministic argmin of an integer cost under the ``(cost, start)``
total-order tie-break.

Current increment: candidates are window starts only and the cost is
constant 0, so argmin with the earliest-start tie-break selects exactly the
first feasible window — behavior-identical to the original first-fit loop
(proven output-identical in ``tests/scheduler/test_scoring.py``). The
intra-window candidate grid and the cost terms activate in the
scoring-terms increment (axiom 05 "Rollout status").
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from agentic_calendar.contracts.common_types import FocusLevel
from agentic_calendar.contracts.task_plan import Task

from .inputs import FreeBusyInterval
from .policy import SchedulingPolicy
from .windows import FreeWindow


@dataclass(slots=True)
class PlacementState:
    """Mutable state threaded through the placement loop."""

    busy: list[FreeBusyInterval]
    minutes_per_day: dict[str, int]
    last_deep_end: dict[str, datetime]


@dataclass(frozen=True, slots=True)
class PlacementCandidate:
    """One feasible (start, end) placement inside a specific free window.

    Derived facts a scoring term needs (day key, used minutes, adjacency)
    are computed by the term functions from the candidate plus the loop
    state — never cached here.
    """

    start: datetime
    end: datetime
    window: FreeWindow


def day_key(dt: datetime) -> str:
    """Local-date bucket key for daily-load bookkeeping."""
    return dt.date().isoformat()


def enumerate_candidates(
    task: Task,
    windows: list[FreeWindow],
    state: PlacementState,
    policy: SchedulingPolicy,
) -> list[PlacementCandidate]:
    """Return every feasible candidate placement for ``task``.

    Candidates are window starts only. Each candidate must pass the same
    five hard checks the first-fit loop applied, in the same order: window
    size, deep-window requirement, window-end bound, daily study cap, and
    the break-between-deep-blocks gap. Scoring never relaxes a hard check
    (axiom 05).
    """
    needs_deep = task.required_focus_level is FocusLevel.DEEP
    duration = task.estimated_duration_min
    candidates: list[PlacementCandidate] = []
    for window in _live_windows(windows, state.busy):
        if window.duration_min < duration:
            continue
        if needs_deep and policy.respect_deep_work_windows and not window.is_deep_work:
            continue
        candidate_start = window.start
        candidate_end = candidate_start + timedelta(minutes=duration)
        if candidate_end > window.end:
            continue
        key = day_key(candidate_start)
        used_today = state.minutes_per_day.get(key, 0)
        if used_today + duration > policy.max_daily_study_min:
            continue
        if needs_deep:
            last = state.last_deep_end.get(key)
            if last is not None:
                gap = (candidate_start - last).total_seconds() / 60
                if gap < policy.min_break_between_deep_blocks_min:
                    continue
        candidates.append(
            PlacementCandidate(start=candidate_start, end=candidate_end, window=window)
        )
    return candidates


def candidate_cost(candidate: PlacementCandidate) -> int:
    """Integer cost of a candidate (axiom 05 scored placement).

    Constant 0 until the scoring terms land; argmin with the earliest-start
    tie-break therefore reproduces first fit exactly.
    """
    del candidate
    return 0


def select_placement(
    candidates: list[PlacementCandidate],
) -> PlacementCandidate | None:
    """Deterministic argmin under the total-order key ``(cost, start)``.

    Free windows are disjoint and starts within a window are distinct, so no
    two candidates share a ``start`` — the key is a total order and the
    selection is unique.
    """
    if not candidates:
        return None
    return min(candidates, key=lambda c: (candidate_cost(c), c.start))


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
