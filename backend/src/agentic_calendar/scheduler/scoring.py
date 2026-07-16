"""Placement-candidate machinery for the greedy scheduler.

Axiom 05 "Scored Placement": enumerate every feasible candidate start
(window starts plus a fixed intra-window grid), then pick the deterministic
argmin of an integer cost under the ``(cost, start)`` total-order tie-break.
``rank_placement`` additionally exposes the second-best cost, which powers
the greedy loop's regret-based insertion order (axiom 05 "Insertion
order"): the task with the most to lose places first.

All arithmetic is integer minutes. Soft terms reorder feasible candidates
and never reject one — every hard check the first-fit loop applied is still
applied here, so any task first fit would have placed remains placeable
(the grid strictly adds candidates).

``score_schedule`` re-derives the *schedule-level* term totals from a
finished ``SchedulerOutput`` for the quality report and the polish
objective. Those totals are deliberately not the sum of the marginal
per-placement values (marginals are path-dependent); only the
schedule-level definitions are the audit surface.
"""

from __future__ import annotations

import itertools
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta

from agentic_calendar.contracts.common_types import FocusLevel
from agentic_calendar.contracts.pooled_duration_model import TimeOfDayBand
from agentic_calendar.contracts.scheduler_output import SchedulerOutput
from agentic_calendar.contracts.task_plan import Task
from agentic_calendar.duration_estimation.pooled import derive_time_of_day_band

from .inputs import FreeBusyInterval, SchedulerInput
from .policy import SchedulingPolicy
from .windows import FreeWindow, enumerate_free_windows

_WEEKEND_WEEKDAYS = (5, 6)  # Sat, Sun under datetime.weekday()


@dataclass(frozen=True)
class PlacementScoringConfig:
    """Weights and knobs for scored placement (axiom 05).

    Every value is an integer heuristic prior, journaled as such; the only
    supported override path is ``tuning.toml`` ``[scheduler_placement]``
    (axiom 07).
    """

    w_daily_balance: int = 3
    w_back_to_back: int = 2
    w_fragmentation: int = 1
    w_deep_window_conservation: int = 2
    w_evening_preference: int = 1
    w_weekend_long_block: int = 1
    w_earliness: int = 1
    buffer_min: int = 15
    candidate_grid_min: int = 15


DEFAULT_PLACEMENT_SCORING_CONFIG = PlacementScoringConfig()


@dataclass(frozen=True, slots=True)
class PlacedBlock:
    """A study block this run has already placed (adjacency bookkeeping).

    Only blocks the scheduler placed count for the ``back_to_back`` term —
    external calendar busy does not.
    """

    start: datetime
    end: datetime
    is_deep: bool


@dataclass(slots=True)
class PlacementState:
    """Mutable state threaded through the placement loop."""

    busy: list[FreeBusyInterval]
    minutes_per_day: dict[str, int]
    last_deep_end: dict[str, datetime]
    placed: list[PlacedBlock]


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


def ceil_div(a: int, b: int) -> int:
    """Integer ceiling division (axiom 05: no floats in placement math)."""
    return -(-a // b)


def compute_target_daily_min(inp: SchedulerInput, windows: list[FreeWindow]) -> int:
    """Even-spread daily target for the ``daily_balance`` term.

    ``working_days`` counts distinct local dates carrying at least one free
    window in the *initial* enumeration (before any placement);
    ``total_plan_min`` sums the not-yet-completed plan tasks. With no
    working days nothing places anyway, so the cap stands in.
    """
    working_days = len({w.start.date() for w in windows})
    if working_days == 0:
        return inp.policy.max_daily_study_min
    completed = set(inp.completed_task_ids)
    total_plan_min = sum(
        t.estimated_duration_min
        for t in inp.plan.tasks
        if t.task_id not in completed
    )
    return min(
        inp.policy.max_daily_study_min, ceil_div(total_plan_min, working_days)
    )


def compute_day_quotas(
    inp: SchedulerInput, windows: list[FreeWindow]
) -> dict[str, int]:
    """Per-day soft quotas for the ``daily_balance`` term (axiom 05).

    Every working day (a distinct local date carrying ≥ 1 window in the
    initial enumeration) gets the same even-spread target today — the
    formula has no per-day inputs yet — but the term reads a precomputed
    map so per-day refinement (and tests) can override individual days.
    A day absent from the map has no enumerated free capacity; consumers
    treat its quota as 0.
    """
    target = compute_target_daily_min(inp, windows)
    return {day: target for day in sorted({day_key(w.start) for w in windows})}


def enumerate_candidates(
    task: Task,
    windows: list[FreeWindow],
    state: PlacementState,
    policy: SchedulingPolicy,
    scoring: PlacementScoringConfig,
) -> list[PlacementCandidate]:
    """Return every feasible candidate placement for ``task``.

    Candidate starts are ``window.start + k x candidate_grid_min`` for every
    ``k ≥ 0`` with ``start + duration ≤ window.end`` (the ``k = 0`` element
    is the window start). Each candidate must pass the same five hard checks
    the first-fit loop applied: window size, deep-window requirement,
    window-end bound, daily study cap, and the break-between-deep-blocks
    gap. Scoring never relaxes a hard check (axiom 05). Because a window
    never spans midnight, the size / deep-requirement / daily-cap checks are
    per-window; only the deep-gap check varies with the start — a later
    grid start can satisfy it where the window start does not.
    """
    needs_deep = task.required_focus_level is FocusLevel.DEEP
    duration = task.estimated_duration_min
    grid = timedelta(minutes=scoring.candidate_grid_min)
    candidates: list[PlacementCandidate] = []
    for window in _live_windows(windows, state.busy):
        if window.duration_min < duration:
            continue
        if needs_deep and policy.respect_deep_work_windows and not window.is_deep_work:
            continue
        key = day_key(window.start)
        used_today = state.minutes_per_day.get(key, 0)
        if used_today + duration > policy.max_daily_study_min:
            continue
        last_deep = state.last_deep_end.get(key) if needs_deep else None
        candidate_start = window.start
        while candidate_start + timedelta(minutes=duration) <= window.end:
            if last_deep is None or _gap_min(last_deep, candidate_start) >= (
                policy.min_break_between_deep_blocks_min
            ):
                candidates.append(
                    PlacementCandidate(
                        start=candidate_start,
                        end=candidate_start + timedelta(minutes=duration),
                        window=window,
                    )
                )
            candidate_start += grid
    return candidates


def _gap_min(earlier: datetime, later: datetime) -> int:
    """Whole minutes from ``earlier`` to ``later`` (non-negative by caller)."""
    return int((later - earlier).total_seconds() // 60)


# --------------------------------------------------------------------------- #
# Cost terms — exact formulas pinned in
# docs/implementation-plans/scheduler-placement-quality/01-scored-placement.md
# --------------------------------------------------------------------------- #


def daily_balance_penalty(
    candidate: PlacementCandidate,
    task: Task,
    state: PlacementState,
    day_quotas: Mapping[str, int],
) -> int:
    """Minutes the candidate pushes its day past that day's soft quota.

    A day missing from the map carries no enumerated free capacity, so its
    quota is 0 — every placed minute there counts as overflow. Quotas are
    soft: they reorder candidates, never reject one.
    """
    key = day_key(candidate.start)
    used_today = state.minutes_per_day.get(key, 0)
    return max(0, used_today + task.estimated_duration_min - day_quotas.get(key, 0))


def back_to_back_penalty(
    candidate: PlacementCandidate,
    task: Task,
    state: PlacementState,
    policy: SchedulingPolicy,
    scoring: PlacementScoringConfig,
) -> int:
    """Buffer shortfall against the nearest placed study block on each side.

    Per side: if the nearest same-day placed block sits closer than
    ``buffer_min``, add ``buffer_min - gap``; the side's contribution doubles
    iff ``avoid_back_to_back_deep_work``, the candidate task is deep, and
    that adjacent block is deep. External calendar busy never counts.
    """
    key = day_key(candidate.start)
    task_is_deep = task.required_focus_level is FocusLevel.DEEP
    before: PlacedBlock | None = None
    after: PlacedBlock | None = None
    for block in state.placed:
        if day_key(block.start) != key:
            continue
        if block.end <= candidate.start and (before is None or block.end > before.end):
            before = block
        elif block.start >= candidate.end and (
            after is None or block.start < after.start
        ):
            after = block
    total = 0
    for neighbor, gap in (
        (before, _gap_min(before.end, candidate.start) if before else 0),
        (after, _gap_min(candidate.end, after.start) if after else 0),
    ):
        if neighbor is None or gap >= scoring.buffer_min:
            continue
        side = scoring.buffer_min - gap
        if policy.avoid_back_to_back_deep_work and task_is_deep and neighbor.is_deep:
            side *= 2
        total += side
    return total


def fragmentation_penalty(
    candidate: PlacementCandidate, policy: SchedulingPolicy
) -> int:
    """Sliver minutes the placement strands on either side of its window."""

    def sliver(minutes: int) -> int:
        return minutes if 0 < minutes < policy.preferred_session_length_min else 0

    lead = _gap_min(candidate.window.start, candidate.start)
    trail = _gap_min(candidate.end, candidate.window.end)
    return sliver(lead) + sliver(trail)


def deep_window_conservation_penalty(
    candidate: PlacementCandidate, task: Task
) -> int:
    """Opportunity cost of a non-deep task consuming scarce deep capacity."""
    if candidate.window.is_deep_work and task.required_focus_level is not FocusLevel.DEEP:
        return task.estimated_duration_min
    return 0


def earliness_penalty(candidate: PlacementCandidate, horizon_start: datetime) -> int:
    """Days from horizon start to the candidate's local date.

    Deliberately tiny (unit = days, default weight 1): the minutes-scaled
    terms dominate it, so it acts only as fill-earlier tie pressure — a
    pure balance objective would otherwise scatter work arbitrarily late.
    """
    return (candidate.start.date() - horizon_start.date()).days


def evening_preference_bonus(
    candidate: PlacementCandidate, task: Task, policy: SchedulingPolicy
) -> int:
    """Evening-band start when the user prefers evening sessions.

    Scheduler datetimes are already user-local wall-clock, so the band comes
    straight from the start hour (shared band definition — never a second
    one).
    """
    if (
        policy.prefer_evening_sessions
        and derive_time_of_day_band(candidate.start.hour) is TimeOfDayBand.EVENING
    ):
        return task.estimated_duration_min
    return 0


def weekend_long_block_bonus(
    candidate: PlacementCandidate, task: Task, policy: SchedulingPolicy
) -> int:
    """Weekend placement of a longer-than-preferred block, when preferred."""
    if (
        policy.prefer_weekend_long_blocks
        and policy.allow_weekends
        and candidate.start.date().weekday() in _WEEKEND_WEEKDAYS
        and task.estimated_duration_min > policy.preferred_session_length_min
    ):
        return task.estimated_duration_min
    return 0


def candidate_cost(
    candidate: PlacementCandidate,
    *,
    task: Task,
    state: PlacementState,
    policy: SchedulingPolicy,
    scoring: PlacementScoringConfig,
    day_quotas: Mapping[str, int],
    horizon_start: datetime,
) -> int:
    """Integer cost of a candidate (axiom 05 scored placement).

    ``cost = Σ w·penalty - Σ w·bonus``; every penalty/bonus is a
    non-negative int (minutes-scaled except the day-scaled ``earliness``)
    and every weight an int.
    """
    return (
        scoring.w_daily_balance
        * daily_balance_penalty(candidate, task, state, day_quotas)
        + scoring.w_back_to_back
        * back_to_back_penalty(candidate, task, state, policy, scoring)
        + scoring.w_fragmentation * fragmentation_penalty(candidate, policy)
        + scoring.w_deep_window_conservation
        * deep_window_conservation_penalty(candidate, task)
        + scoring.w_earliness * earliness_penalty(candidate, horizon_start)
        - scoring.w_evening_preference
        * evening_preference_bonus(candidate, task, policy)
        - scoring.w_weekend_long_block
        * weekend_long_block_bonus(candidate, task, policy)
    )


@dataclass(frozen=True, slots=True)
class PlacementRanking:
    """A task's best candidate plus the facts the insertion order needs.

    ``regret = second_best_cost - cost`` measures how much the task loses
    if its best slot is taken (0 when the two cheapest candidates tie). A
    single-candidate task has no second-best; the flag — not an infinity
    sentinel — encodes "place me first" (axiom 05 "Insertion order").
    """

    candidate: PlacementCandidate
    cost: int
    second_best_cost: int | None

    @property
    def single_candidate(self) -> bool:
        return self.second_best_cost is None

    @property
    def regret(self) -> int:
        if self.second_best_cost is None:
            return 0
        return self.second_best_cost - self.cost


def rank_placement(
    candidates: list[PlacementCandidate],
    *,
    task: Task,
    state: PlacementState,
    policy: SchedulingPolicy,
    scoring: PlacementScoringConfig,
    day_quotas: Mapping[str, int],
    horizon_start: datetime,
) -> PlacementRanking | None:
    """Rank a task's candidates: the ``(cost, start)`` argmin plus regret.

    Returns ``None`` for an empty candidate list — the caller fails the
    task through its typed reason path.
    """
    if not candidates:
        return None
    scored = [
        (
            candidate_cost(
                c,
                task=task,
                state=state,
                policy=policy,
                scoring=scoring,
                day_quotas=day_quotas,
                horizon_start=horizon_start,
            ),
            c,
        )
        for c in candidates
    ]
    best_cost, best = min(scored, key=lambda pair: (pair[0], pair[1].start))
    if len(scored) == 1:
        return PlacementRanking(candidate=best, cost=best_cost, second_best_cost=None)
    second_best_cost = sorted(cost for cost, _ in scored)[1]
    return PlacementRanking(
        candidate=best, cost=best_cost, second_best_cost=second_best_cost
    )


def select_placement(
    candidates: list[PlacementCandidate],
    *,
    task: Task,
    state: PlacementState,
    policy: SchedulingPolicy,
    scoring: PlacementScoringConfig,
    day_quotas: Mapping[str, int],
    horizon_start: datetime,
) -> PlacementCandidate | None:
    """Deterministic argmin under the total-order key ``(cost, start)``.

    Free windows are disjoint and grid starts within a window are distinct,
    so no two candidates share a ``start`` — the key is a total order and
    the selection is unique.
    """
    ranking = rank_placement(
        candidates,
        task=task,
        state=state,
        policy=policy,
        scoring=scoring,
        day_quotas=day_quotas,
        horizon_start=horizon_start,
    )
    return None if ranking is None else ranking.candidate


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


# --------------------------------------------------------------------------- #
# Schedule-level scoring — the quality-report / polish objective
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ScheduleScoreBreakdown:
    """Schedule-level term totals re-derived from a finished schedule.

    ``total_cost`` follows the same sign convention as placement
    (``Σ w·penalty - Σ w·bonus``) but over the schedule-level definitions —
    deliberately not the sum of the path-dependent marginal values.
    """

    daily_balance_total: int
    back_to_back_total: int
    fragmentation_total: int
    deep_window_conservation_total: int
    earliness_total: int
    evening_preference_total: int
    weekend_long_block_total: int
    total_cost: int
    target_daily_min: int
    scheduled_count: int
    unscheduled_count: int
    per_day_minutes: dict[str, int]
    band_histogram: dict[str, int]


@dataclass(frozen=True)
class BlockScoreTotals:
    """Schedule-level term totals over a set of placed blocks.

    The single scoring engine shared by ``score_schedule`` (quality report)
    and the bounded polish pass (axiom 05 "Bounded polish pass") — the
    polish objective is these totals by construction, never a re-derivation.
    """

    daily_balance_total: int
    back_to_back_total: int
    fragmentation_total: int
    deep_window_conservation_total: int
    earliness_total: int
    evening_preference_total: int
    weekend_long_block_total: int
    total_cost: int
    per_day_minutes: dict[str, int]
    band_histogram: dict[str, int]


def score_schedule(
    output: SchedulerOutput,
    inp: SchedulerInput,
    scoring: PlacementScoringConfig = DEFAULT_PLACEMENT_SCORING_CONFIG,
) -> ScheduleScoreBreakdown:
    """Compute the schedule-level totals for a finished ``SchedulerOutput``.

    Pure and read-only: re-enumerates windows from the input, never mutates
    either artifact, and works for any output produced from ``inp``
    (including partial failures — unscheduled tasks simply carry no blocks).
    """
    tasks_by_id = {t.task_id: t for t in inp.plan.tasks}
    initial_windows = enumerate_free_windows(
        horizon_start=inp.horizon_start,
        horizon_end=inp.horizon_end,
        free_busy=list(inp.calendar_free_busy),
        policy=inp.policy,
    )
    target_daily_min = compute_target_daily_min(inp, initial_windows)
    day_quotas = compute_day_quotas(inp, initial_windows)

    blocks = [
        PlacedBlock(
            start=st.start,
            end=st.end,
            is_deep=(
                tasks_by_id[st.task_id].required_focus_level is FocusLevel.DEEP
            ),
        )
        for st in output.scheduled_tasks
    ]
    totals = score_blocks(
        blocks,
        inp,
        scoring,
        initial_windows=initial_windows,
        day_quotas=day_quotas,
    )
    return ScheduleScoreBreakdown(
        daily_balance_total=totals.daily_balance_total,
        back_to_back_total=totals.back_to_back_total,
        fragmentation_total=totals.fragmentation_total,
        deep_window_conservation_total=totals.deep_window_conservation_total,
        earliness_total=totals.earliness_total,
        evening_preference_total=totals.evening_preference_total,
        weekend_long_block_total=totals.weekend_long_block_total,
        total_cost=totals.total_cost,
        target_daily_min=target_daily_min,
        scheduled_count=len(output.scheduled_tasks),
        unscheduled_count=len(output.unscheduled_tasks),
        per_day_minutes=totals.per_day_minutes,
        band_histogram=totals.band_histogram,
    )


def score_blocks(
    blocks: list[PlacedBlock],
    inp: SchedulerInput,
    scoring: PlacementScoringConfig,
    *,
    initial_windows: list[FreeWindow],
    day_quotas: Mapping[str, int],
) -> BlockScoreTotals:
    """Schedule-level totals for an arbitrary placed-block set.

    ``initial_windows`` / ``day_quotas`` are passed in (not recomputed) so a
    caller evaluating many hypothetical block sets — the polish pass — pays
    the input-only derivations once.
    """
    blocks = sorted(blocks, key=lambda b: b.start)

    per_day_minutes: dict[str, int] = {}
    band_histogram: dict[str, int] = {}
    for block in blocks:
        key = day_key(block.start)
        per_day_minutes[key] = per_day_minutes.get(key, 0) + _gap_min(
            block.start, block.end
        )
        band = derive_time_of_day_band(block.start.hour).value
        band_histogram[band] = band_histogram.get(band, 0) + 1

    daily_balance_total = sum(
        max(0, minutes - day_quotas.get(day, 0))
        for day, minutes in per_day_minutes.items()
    )
    earliness_total = sum(
        (block.start.date() - inp.horizon_start.date()).days for block in blocks
    )

    back_to_back_total = 0
    for earlier, later in itertools.pairwise(blocks):
        if day_key(earlier.start) != day_key(later.start):
            continue
        gap = _gap_min(earlier.end, later.start)
        if gap >= scoring.buffer_min:
            continue
        pair = scoring.buffer_min - gap
        if (
            inp.policy.avoid_back_to_back_deep_work
            and earlier.is_deep
            and later.is_deep
        ):
            pair *= 2
        back_to_back_total += pair

    final_busy = list(inp.calendar_free_busy) + [
        FreeBusyInterval(start=b.start, end=b.end) for b in blocks
    ]
    final_windows = enumerate_free_windows(
        horizon_start=inp.horizon_start,
        horizon_end=inp.horizon_end,
        free_busy=final_busy,
        policy=inp.policy,
    )
    fragmentation_total = sum(
        w.duration_min
        for w in final_windows
        if 0 < w.duration_min < inp.policy.preferred_session_length_min
    )

    deep_windows = [w for w in initial_windows if w.is_deep_work]
    deep_window_conservation_total = 0
    evening_preference_total = 0
    weekend_long_block_total = 0
    for block in blocks:
        duration = _gap_min(block.start, block.end)
        if not block.is_deep:
            deep_window_conservation_total += sum(
                _overlap_min(block, w) for w in deep_windows
            )
        if (
            inp.policy.prefer_evening_sessions
            and derive_time_of_day_band(block.start.hour) is TimeOfDayBand.EVENING
        ):
            evening_preference_total += duration
        if (
            inp.policy.prefer_weekend_long_blocks
            and inp.policy.allow_weekends
            and block.start.date().weekday() in _WEEKEND_WEEKDAYS
            and duration > inp.policy.preferred_session_length_min
        ):
            weekend_long_block_total += duration

    total_cost = (
        scoring.w_daily_balance * daily_balance_total
        + scoring.w_back_to_back * back_to_back_total
        + scoring.w_fragmentation * fragmentation_total
        + scoring.w_deep_window_conservation * deep_window_conservation_total
        + scoring.w_earliness * earliness_total
        - scoring.w_evening_preference * evening_preference_total
        - scoring.w_weekend_long_block * weekend_long_block_total
    )
    return BlockScoreTotals(
        daily_balance_total=daily_balance_total,
        back_to_back_total=back_to_back_total,
        fragmentation_total=fragmentation_total,
        deep_window_conservation_total=deep_window_conservation_total,
        earliness_total=earliness_total,
        evening_preference_total=evening_preference_total,
        weekend_long_block_total=weekend_long_block_total,
        total_cost=total_cost,
        per_day_minutes=per_day_minutes,
        band_histogram=band_histogram,
    )


def _overlap_min(block: PlacedBlock, window: FreeWindow) -> int:
    """Whole minutes of overlap between a placed block and a window."""
    start = max(block.start, window.start)
    end = min(block.end, window.end)
    if end <= start:
        return 0
    return _gap_min(start, end)
