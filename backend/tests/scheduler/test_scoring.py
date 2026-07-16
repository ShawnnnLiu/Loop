"""Scored-placement tests (axiom 05 "Scored Placement").

Covers the candidate grid, each cost term in isolation (two-window fixtures
where only that term discriminates), the ``(cost, start)`` tie-break, the
regret ranking that powers insertion order, byte-level determinism, and the
phase acceptance fixtures (5 tasks x 3 free days spreads across days
instead of stacking day 1; 6 equal tasks x 3 equal days land 2/2/2).

The P-B first-fit equivalence proof (``_first_fit_reference``) was deleted
when the scoring terms landed — the equivalence deliberately stopped
holding. The all-weights-zero test below pins the surviving relationship:
zero weights reduce each *placement* to earliest-feasible-start (see the
``ZERO_WEIGHTS`` note in ``_helpers`` for the insertion-order caveat).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from agentic_calendar.contracts.task_plan import Task
from agentic_calendar.scheduler import schedule
from agentic_calendar.scheduler.policy import SchedulingPolicy
from agentic_calendar.scheduler.scoring import (
    DEFAULT_PLACEMENT_SCORING_CONFIG,
    PlacedBlock,
    PlacementCandidate,
    PlacementScoringConfig,
    PlacementState,
    back_to_back_penalty,
    compute_day_quotas,
    compute_target_daily_min,
    daily_balance_penalty,
    deep_window_conservation_penalty,
    earliness_penalty,
    enumerate_candidates,
    evening_preference_bonus,
    fragmentation_penalty,
    rank_placement,
    score_schedule,
    select_placement,
    weekend_long_block_bonus,
)
from agentic_calendar.scheduler.windows import FreeWindow
from tests.scheduler._helpers import (
    DEEP_WORK_POLICY,
    DEFAULT_POLICY,
    ZERO_WEIGHTS,
    busy,
    make_input,
    make_plan,
    make_task,
)

MONDAY = datetime(2026, 5, 4, 0, 0, tzinfo=UTC)
SCORING = DEFAULT_PLACEMENT_SCORING_CONFIG

#: A week of effectively-unconstraining quotas so term tests that are not
#: about daily balance see a zero balance penalty everywhere.
WEEK_QUOTAS = {
    (MONDAY + timedelta(days=d)).date().isoformat(): 240 for d in range(7)
}


def _window(start: datetime, minutes: int, *, deep: bool = False) -> FreeWindow:
    return FreeWindow(
        start=start, end=start + timedelta(minutes=minutes), is_deep_work=deep
    )


def _candidate(
    window: FreeWindow, *, offset_min: int = 0, duration_min: int = 60
) -> PlacementCandidate:
    start = window.start + timedelta(minutes=offset_min)
    return PlacementCandidate(
        start=start, end=start + timedelta(minutes=duration_min), window=window
    )


def _fresh_state() -> PlacementState:
    return PlacementState(busy=[], minutes_per_day={}, last_deep_end={}, placed=[])


def _task(**overrides: object) -> Task:
    return Task.model_validate(make_task(**overrides))  # type: ignore[arg-type]


def _select(
    candidates: list[PlacementCandidate],
    *,
    task: Task,
    state: PlacementState | None = None,
    policy: SchedulingPolicy = DEFAULT_POLICY,
    scoring: PlacementScoringConfig = SCORING,
    day_quotas: dict[str, int] | None = None,
    horizon_start: datetime = MONDAY,
) -> PlacementCandidate | None:
    return select_placement(
        candidates,
        task=task,
        state=state if state is not None else _fresh_state(),
        policy=policy,
        scoring=scoring,
        day_quotas=day_quotas if day_quotas is not None else WEEK_QUOTAS,
        horizon_start=horizon_start,
    )


def _rank(
    candidates: list[PlacementCandidate],
    *,
    task: Task,
    state: PlacementState | None = None,
    policy: SchedulingPolicy = DEFAULT_POLICY,
    scoring: PlacementScoringConfig = SCORING,
    day_quotas: dict[str, int] | None = None,
    horizon_start: datetime = MONDAY,
):
    return rank_placement(
        candidates,
        task=task,
        state=state if state is not None else _fresh_state(),
        policy=policy,
        scoring=scoring,
        day_quotas=day_quotas if day_quotas is not None else WEEK_QUOTAS,
        horizon_start=horizon_start,
    )


# --------------------------------------------------------------------------- #
# Candidate enumeration — grid + hard checks
# --------------------------------------------------------------------------- #


def test_enumerate_candidates_walks_the_intra_window_grid() -> None:
    """A 90-min window yields grid starts at +0/+15/+30 for a 60-min task."""
    task = _task(task_id="t", estimated_duration_min=60)
    w_short = _window(MONDAY.replace(hour=8), 30)  # too small — no candidates
    w_fit = _window(MONDAY.replace(hour=9), 90)
    candidates = enumerate_candidates(
        task, [w_short, w_fit], _fresh_state(), DEFAULT_POLICY, SCORING
    )
    assert [(c.start, c.window) for c in candidates] == [
        (w_fit.start, w_fit),
        (w_fit.start + timedelta(minutes=15), w_fit),
        (w_fit.start + timedelta(minutes=30), w_fit),
    ]
    assert all(c.end - c.start == timedelta(minutes=60) for c in candidates)
    assert all(c.end <= w_fit.end for c in candidates)


def test_enumerate_candidates_grid_step_follows_config() -> None:
    task = _task(task_id="t", estimated_duration_min=60)
    w = _window(MONDAY.replace(hour=9), 120)
    wide_grid = PlacementScoringConfig(candidate_grid_min=30)
    candidates = enumerate_candidates(
        task, [w], _fresh_state(), DEFAULT_POLICY, wide_grid
    )
    assert [c.start for c in candidates] == [
        w.start,
        w.start + timedelta(minutes=30),
        w.start + timedelta(minutes=60),
    ]


def test_enumerate_candidates_applies_daily_cap_per_window() -> None:
    """A day at the study cap yields no candidates anywhere in that day."""
    capped = DEFAULT_POLICY.model_copy(update={"max_daily_study_min": 120})
    task = _task(task_id="t", estimated_duration_min=60)
    monday = _window(MONDAY.replace(hour=9), 120)
    tuesday = _window(MONDAY.replace(hour=9) + timedelta(days=1), 120)
    over_cap = PlacementState(
        busy=[], minutes_per_day={"2026-05-04": 90}, last_deep_end={}, placed=[]
    )
    candidates = enumerate_candidates(task, [monday, tuesday], over_cap, capped, SCORING)
    assert {day for day in (c.start.date().isoformat() for c in candidates)} == {
        "2026-05-05"
    }


def test_enumerate_candidates_deep_gap_admits_later_grid_starts() -> None:
    """The grid fixes the first-fit blind spot: a deep task rejected at the
    window start (break-between-deep-blocks) is admitted at the first grid
    start that satisfies the gap, instead of losing the whole window."""
    task = _task(task_id="d", estimated_duration_min=60, required_focus_level="deep")
    monday_deep = _window(MONDAY.replace(hour=19), 120, deep=True)
    state = PlacementState(
        busy=[],
        minutes_per_day={"2026-05-04": 60},
        last_deep_end={"2026-05-04": MONDAY.replace(hour=19)},
        placed=[],
    )
    candidates = enumerate_candidates(
        task, [monday_deep], state, DEEP_WORK_POLICY, SCORING
    )
    # min_break_between_deep_blocks_min=30 → 19:00 and 19:15 fail, 19:30+ pass.
    assert [c.start for c in candidates] == [
        MONDAY.replace(hour=19, minute=30),
        MONDAY.replace(hour=19, minute=45),
        MONDAY.replace(hour=20),
    ]


def test_enumerate_candidates_deep_task_needs_deep_window() -> None:
    task = _task(task_id="d", estimated_duration_min=60, required_focus_level="deep")
    shallow = _window(MONDAY.replace(hour=9), 120)
    deep = _window(MONDAY.replace(hour=19), 120, deep=True)
    candidates = enumerate_candidates(
        task, [shallow, deep], _fresh_state(), DEEP_WORK_POLICY, SCORING
    )
    assert all(c.window is deep for c in candidates)


# --------------------------------------------------------------------------- #
# Selection — argmin under (cost, start)
# --------------------------------------------------------------------------- #


def test_select_placement_empty_returns_none() -> None:
    assert _select([], task=_task(task_id="t")) is None


def test_select_placement_breaks_cost_ties_by_earliest_start() -> None:
    """Two exact-fit windows on empty days score identically → earliest wins."""
    task = _task(task_id="t", estimated_duration_min=60)
    early = _window(MONDAY.replace(hour=9), 60)
    late = _window(MONDAY.replace(hour=9) + timedelta(days=1), 60)
    chosen = _select(
        [_candidate(late), _candidate(early)],
        task=task,
    )
    assert chosen is not None
    assert chosen.start == early.start


def test_all_zero_weights_reduce_to_earliest_feasible_start() -> None:
    """With every weight zero the argmin over (0, start) is first fit."""
    plan = make_plan(
        *[make_task(task_id=f"t_{i}", estimated_duration_min=60) for i in range(5)]
    )
    out = schedule(make_input(plan, horizon_days=3), scoring=ZERO_WEIGHTS)
    starts = [st.start for st in out.scheduled_tasks]
    # Back-to-back from 08:00 until the 240-min daily cap, then next day.
    assert starts == [
        MONDAY.replace(hour=8),
        MONDAY.replace(hour=9),
        MONDAY.replace(hour=10),
        MONDAY.replace(hour=11),
        MONDAY.replace(hour=8) + timedelta(days=1),
    ]


# --------------------------------------------------------------------------- #
# Per-term unit tests — fixtures where only that term discriminates
# --------------------------------------------------------------------------- #


def test_daily_balance_penalty_values() -> None:
    task = _task(task_id="t", estimated_duration_min=60)
    w = _window(MONDAY.replace(hour=9), 60)
    state = _fresh_state()
    quotas = {"2026-05-04": 100}
    assert daily_balance_penalty(_candidate(w), task, state, quotas) == 0
    state.minutes_per_day["2026-05-04"] = 80
    assert daily_balance_penalty(_candidate(w), task, state, quotas) == 40
    # A day absent from the map has no enumerated capacity — quota 0.
    assert daily_balance_penalty(_candidate(w), task, state, {}) == 140


def test_daily_balance_steers_to_the_lighter_day() -> None:
    task = _task(task_id="t", estimated_duration_min=60)
    loaded_day = _window(MONDAY.replace(hour=9), 60)
    empty_day = _window(MONDAY.replace(hour=9) + timedelta(days=1), 60)
    state = _fresh_state()
    state.minutes_per_day["2026-05-04"] = 60
    chosen = _select(
        [_candidate(loaded_day), _candidate(empty_day)],
        task=task,
        state=state,
        day_quotas={"2026-05-04": 60, "2026-05-05": 60},
    )
    assert chosen is not None
    assert chosen.start == empty_day.start


def test_daily_balance_reads_per_day_quotas() -> None:
    """Distinct per-day quotas steer placement — the map is not just a
    uniform target in disguise (P-F: tests can override individual days)."""
    task = _task(task_id="t", estimated_duration_min=60)
    monday = _window(MONDAY.replace(hour=9), 60)
    tuesday = _window(MONDAY.replace(hour=9) + timedelta(days=1), 60)
    quota_free_tuesday = {"2026-05-04": 0, "2026-05-05": 240}
    chosen = _select(
        [_candidate(monday), _candidate(tuesday)],
        task=task,
        day_quotas=quota_free_tuesday,
    )
    assert chosen is not None
    assert chosen.start == tuesday.start


def test_compute_day_quotas_uniform_map_over_working_days() -> None:
    plan = make_plan(
        make_task(task_id="a", estimated_duration_min=100),
        make_task(task_id="b", estimated_duration_min=100),
        make_task(task_id="c", estimated_duration_min=100),
    )
    inp = make_input(plan)
    windows = [
        _window(MONDAY.replace(hour=9), 120),
        _window(MONDAY.replace(hour=14), 60),  # same day — one working day
        _window(MONDAY.replace(hour=9) + timedelta(days=1), 120),
    ]
    # Same value per day (the formula has no per-day inputs yet).
    assert compute_day_quotas(inp, windows) == {
        "2026-05-04": 150,
        "2026-05-05": 150,
    }
    # No windows → no working days → empty map.
    assert compute_day_quotas(inp, []) == {}


def test_back_to_back_penalty_shortfall_and_sides() -> None:
    task = _task(task_id="t", estimated_duration_min=60)
    w = _window(MONDAY.replace(hour=10), 60)
    state = _fresh_state()
    state.placed.append(
        PlacedBlock(
            start=MONDAY.replace(hour=9), end=MONDAY.replace(hour=10), is_deep=False
        )
    )
    # gap 0 → full buffer shortfall
    assert back_to_back_penalty(_candidate(w), task, state, DEFAULT_POLICY, SCORING) == 15
    # gap 10 → shortfall 5
    w_gap10 = _window(MONDAY.replace(hour=10, minute=10), 60)
    assert (
        back_to_back_penalty(_candidate(w_gap10), task, state, DEFAULT_POLICY, SCORING)
        == 5
    )
    # gap ≥ buffer → 0
    w_clear = _window(MONDAY.replace(hour=10, minute=15), 60)
    assert (
        back_to_back_penalty(_candidate(w_clear), task, state, DEFAULT_POLICY, SCORING)
        == 0
    )
    # both sides accumulate
    state.placed.append(
        PlacedBlock(
            start=MONDAY.replace(hour=11, minute=5),
            end=MONDAY.replace(hour=12),
            is_deep=False,
        )
    )
    assert (
        back_to_back_penalty(_candidate(w), task, state, DEFAULT_POLICY, SCORING)
        == 15 + 10
    )


def test_back_to_back_doubles_for_adjacent_deep_blocks_when_avoided() -> None:
    avoid = DEFAULT_POLICY.model_copy(update={"avoid_back_to_back_deep_work": True})
    deep_task = _task(
        task_id="d", estimated_duration_min=60, required_focus_level="deep"
    )
    w = _window(MONDAY.replace(hour=10), 60, deep=True)
    state = _fresh_state()
    state.placed.append(
        PlacedBlock(
            start=MONDAY.replace(hour=9), end=MONDAY.replace(hour=10), is_deep=True
        )
    )
    assert back_to_back_penalty(_candidate(w), deep_task, state, avoid, SCORING) == 30
    # Without the preference the same adjacency costs the plain shortfall.
    assert (
        back_to_back_penalty(_candidate(w), deep_task, state, DEFAULT_POLICY, SCORING)
        == 15
    )
    # A non-deep neighbor never doubles, even with the preference on.
    state.placed[0] = PlacedBlock(
        start=MONDAY.replace(hour=9), end=MONDAY.replace(hour=10), is_deep=False
    )
    assert back_to_back_penalty(_candidate(w), deep_task, state, avoid, SCORING) == 15


def test_back_to_back_ignores_external_calendar_busy() -> None:
    """Only blocks this run placed count — external busy is not a study block."""
    task = _task(task_id="t", estimated_duration_min=60)
    w = _window(MONDAY.replace(hour=10), 60)
    state = _fresh_state()
    state.busy.append(busy(MONDAY.replace(hour=9), minutes=60))
    assert back_to_back_penalty(_candidate(w), task, state, DEFAULT_POLICY, SCORING) == 0


def test_back_to_back_steers_away_from_adjacency() -> None:
    task = _task(task_id="t", estimated_duration_min=60)
    state = _fresh_state()
    state.placed.append(
        PlacedBlock(
            start=MONDAY.replace(hour=9), end=MONDAY.replace(hour=10), is_deep=False
        )
    )
    adjacent = _window(MONDAY.replace(hour=10), 60)
    buffered = _window(MONDAY.replace(hour=11, minute=30), 60)
    chosen = _select(
        [_candidate(adjacent), _candidate(buffered)], task=task, state=state
    )
    assert chosen is not None
    assert chosen.start == buffered.start


def test_fragmentation_penalty_counts_both_slivers() -> None:
    task_duration = 60
    w = _window(MONDAY.replace(hour=9), 120)
    assert fragmentation_penalty(
        _candidate(w, offset_min=0, duration_min=task_duration), DEFAULT_POLICY
    ) == 0  # lead 0, trail 60 (usable)
    assert fragmentation_penalty(
        _candidate(w, offset_min=15, duration_min=task_duration), DEFAULT_POLICY
    ) == 15 + 45  # lead sliver + trail sliver
    assert fragmentation_penalty(
        _candidate(w, offset_min=60, duration_min=task_duration), DEFAULT_POLICY
    ) == 0  # lead 60 (usable), trail 0


def test_fragmentation_steers_to_the_exact_fit_window() -> None:
    """A 60-min task prefers the exact-fit window over stranding a sliver."""
    task = _task(task_id="t", estimated_duration_min=60)
    slivered = _window(MONDAY.replace(hour=9), 90)  # any placement strands 30
    exact = _window(MONDAY.replace(hour=12), 60)
    candidates = enumerate_candidates(
        task, [slivered, exact], _fresh_state(), DEFAULT_POLICY, SCORING
    )
    chosen = _select(candidates, task=task)
    assert chosen is not None
    assert chosen.window == exact


def test_deep_window_conservation_penalty_and_steering() -> None:
    shallow_task = _task(task_id="t", estimated_duration_min=60)
    deep_w = _window(MONDAY.replace(hour=9), 60, deep=True)
    plain_w = _window(MONDAY.replace(hour=12), 60)
    assert deep_window_conservation_penalty(_candidate(deep_w), shallow_task) == 60
    assert deep_window_conservation_penalty(_candidate(plain_w), shallow_task) == 0
    deep_task = _task(
        task_id="d", estimated_duration_min=60, required_focus_level="deep"
    )
    assert deep_window_conservation_penalty(_candidate(deep_w), deep_task) == 0
    chosen = _select(
        [_candidate(deep_w), _candidate(plain_w)],
        task=shallow_task,
        policy=DEEP_WORK_POLICY,
    )
    assert chosen is not None
    assert chosen.window == plain_w


def test_evening_preference_bonus_and_steering() -> None:
    evening_policy = DEFAULT_POLICY.model_copy(
        update={"prefer_evening_sessions": True}
    )
    task = _task(task_id="t", estimated_duration_min=60)
    morning = _window(MONDAY.replace(hour=9), 60)
    evening = _window(MONDAY.replace(hour=18), 60)
    assert evening_preference_bonus(_candidate(morning), task, evening_policy) == 0
    assert evening_preference_bonus(_candidate(evening), task, evening_policy) == 60
    assert evening_preference_bonus(_candidate(evening), task, DEFAULT_POLICY) == 0
    chosen = _select(
        [_candidate(morning), _candidate(evening)], task=task, policy=evening_policy
    )
    assert chosen is not None
    assert chosen.start == evening.start


def test_weekend_long_block_bonus_and_steering() -> None:
    weekend_policy = DEFAULT_POLICY.model_copy(
        update={"prefer_weekend_long_blocks": True}
    )
    long_task = _task(task_id="t", estimated_duration_min=90)
    short_task = _task(task_id="s", estimated_duration_min=60)
    friday = _window(MONDAY.replace(hour=9) + timedelta(days=4), 90)
    saturday = _window(MONDAY.replace(hour=9) + timedelta(days=5), 90)
    assert (
        weekend_long_block_bonus(
            _candidate(saturday, duration_min=90), long_task, weekend_policy
        )
        == 90
    )
    assert (
        weekend_long_block_bonus(
            _candidate(friday, duration_min=90), long_task, weekend_policy
        )
        == 0
    )
    # Not longer than preferred_session_length_min → no bonus.
    assert (
        weekend_long_block_bonus(_candidate(saturday), short_task, weekend_policy) == 0
    )
    # Weekends disallowed → no bonus even when preferred.
    no_weekends = weekend_policy.model_copy(update={"allow_weekends": False})
    assert (
        weekend_long_block_bonus(
            _candidate(saturday, duration_min=90), long_task, no_weekends
        )
        == 0
    )
    chosen = _select(
        [
            _candidate(friday, duration_min=90),
            _candidate(saturday, duration_min=90),
        ],
        task=long_task,
        policy=weekend_policy,
    )
    assert chosen is not None
    assert chosen.start == saturday.start


def test_earliness_penalty_values() -> None:
    same_day = _candidate(_window(MONDAY.replace(hour=22), 60))
    assert earliness_penalty(same_day, MONDAY) == 0
    third_day = _candidate(_window(MONDAY.replace(hour=8) + timedelta(days=3), 60))
    assert earliness_penalty(third_day, MONDAY) == 3
    # Local-date arithmetic: a mid-day horizon start still counts whole days.
    assert earliness_penalty(third_day, MONDAY.replace(hour=13)) == 3


def test_earliness_is_tiny_fill_earlier_pressure() -> None:
    """Earliness (day-scaled) breaks near-ties toward earlier days but never
    outweighs a minutes-scaled term: a 2-min sliver today beats an exact fit
    three days out only because of the earliness term."""
    task = _task(task_id="t", estimated_duration_min=60)
    near_sliver = _window(MONDAY.replace(hour=9), 62)
    far_exact = _window(MONDAY.replace(hour=9) + timedelta(days=3), 60)
    candidates = [
        _candidate(near_sliver, offset_min=2),  # lead sliver 2, trail 0
        _candidate(far_exact),
    ]
    chosen = _select(candidates, task=task)
    assert chosen is not None
    assert chosen.start == near_sliver.start + timedelta(minutes=2)
    # Without the term the exact fit three days out wins on fragmentation.
    no_earliness = PlacementScoringConfig(w_earliness=0)
    chosen = _select(candidates, task=task, scoring=no_earliness)
    assert chosen is not None
    assert chosen.start == far_exact.start


# --------------------------------------------------------------------------- #
# Regret ranking — the insertion-order facts (axiom 05 "Insertion order")
# --------------------------------------------------------------------------- #


def test_rank_placement_empty_returns_none() -> None:
    assert _rank([], task=_task(task_id="t")) is None


def test_rank_placement_single_candidate_sets_the_flag() -> None:
    task = _task(task_id="t", estimated_duration_min=60)
    only = _candidate(_window(MONDAY.replace(hour=9), 60))
    ranking = _rank([only], task=task)
    assert ranking is not None
    assert ranking.candidate == only
    assert ranking.single_candidate
    assert ranking.regret == 0


def test_rank_placement_regret_is_second_best_minus_best() -> None:
    """An exact fit (cost 0) against a full-sliver placement (cost 30):
    regret is the cost gap, and the best candidate is the argmin."""
    task = _task(task_id="t", estimated_duration_min=60)
    exact = _candidate(_window(MONDAY.replace(hour=12), 60))
    slivered = _candidate(_window(MONDAY.replace(hour=9), 90))  # trail 30
    ranking = _rank([slivered, exact], task=task)
    assert ranking is not None
    assert ranking.candidate == exact
    assert ranking.cost == 0
    assert ranking.second_best_cost == 30
    assert ranking.regret == 30
    assert not ranking.single_candidate


def test_rank_placement_tied_best_costs_mean_zero_regret() -> None:
    task = _task(task_id="t", estimated_duration_min=60)
    early = _candidate(_window(MONDAY.replace(hour=9), 60))
    late = _candidate(_window(MONDAY.replace(hour=12), 60))  # same day, same cost
    ranking = _rank([late, early], task=task)
    assert ranking is not None
    assert ranking.candidate == early  # (cost, start) argmin
    assert ranking.regret == 0


def test_compute_target_daily_min() -> None:
    plan = make_plan(
        make_task(task_id="a", estimated_duration_min=100),
        make_task(task_id="b", estimated_duration_min=100),
        make_task(task_id="c", estimated_duration_min=100),
    )
    inp = make_input(plan)
    windows = [
        _window(MONDAY.replace(hour=9), 120),
        _window(MONDAY.replace(hour=14), 60),  # same day — one working day
        _window(MONDAY.replace(hour=9) + timedelta(days=1), 120),
    ]
    # ceil(300 / 2 days) = 150 < max_daily_study_min 240.
    assert compute_target_daily_min(inp, windows) == 150
    # Completed tasks leave the numerator.
    done = make_input(plan, completed_task_ids=["a"])
    assert compute_target_daily_min(done, windows) == 100
    # The daily cap floors the target.
    capped = make_input(plan, policy=DEFAULT_POLICY.model_copy(update={"max_daily_study_min": 120}))
    assert compute_target_daily_min(capped, windows) == 120
    # No working days → the cap stands in (nothing places anyway).
    assert compute_target_daily_min(inp, []) == 240


# --------------------------------------------------------------------------- #
# End-to-end: acceptance fixture, override sensitivity, determinism
# --------------------------------------------------------------------------- #


def test_five_tasks_three_days_spread_instead_of_stacking_day_one() -> None:
    """Phase acceptance: 5 x 60-min tasks over 3 free days no longer pile up
    at day 1 ``no_events_before`` — daily balance spreads them 120/120/60."""
    plan = make_plan(
        *[make_task(task_id=f"t_{i}", estimated_duration_min=60) for i in range(5)]
    )
    out = schedule(make_input(plan, horizon_days=3))
    starts = {st.task_id: st.start for st in out.scheduled_tasks}
    assert starts == {
        "t_0": MONDAY.replace(hour=8),
        "t_1": MONDAY.replace(hour=8) + timedelta(days=1),
        "t_2": MONDAY.replace(hour=8) + timedelta(days=2),
        "t_3": MONDAY.replace(hour=10),
        "t_4": MONDAY.replace(hour=10) + timedelta(days=1),
    }
    per_day: dict[str, int] = {}
    for st in out.scheduled_tasks:
        key = st.start.date().isoformat()
        per_day[key] = per_day.get(key, 0) + 60
    assert per_day == {"2026-05-04": 120, "2026-05-05": 120, "2026-05-06": 60}


def test_six_equal_tasks_over_three_equal_days_land_two_per_day() -> None:
    """P-F acceptance: 6 x 60-min tasks over 3 equally free days spread
    2/2/2 under the per-day soft quotas — never 6/0/0."""
    plan = make_plan(
        *[make_task(task_id=f"t_{i}", estimated_duration_min=60) for i in range(6)]
    )
    out = schedule(make_input(plan, horizon_days=3))
    assert len(out.scheduled_tasks) == 6
    per_day: dict[str, int] = {}
    for st in out.scheduled_tasks:
        key = st.start.date().isoformat()
        per_day[key] = per_day.get(key, 0) + 1
    assert per_day == {"2026-05-04": 2, "2026-05-05": 2, "2026-05-06": 2}


def test_scoring_override_changes_placement() -> None:
    """P-D acceptance: a different weight vector produces a different draft."""
    plan = make_plan(
        *[make_task(task_id=f"t_{i}", estimated_duration_min=60) for i in range(5)]
    )
    default_out = schedule(make_input(plan, horizon_days=3))
    zeroed = schedule(make_input(plan, horizon_days=3), scoring=ZERO_WEIGHTS)
    assert default_out.model_dump() != zeroed.model_dump()


def test_schedule_is_deterministic_byte_for_byte() -> None:
    def build() -> tuple:
        plan = make_plan(
            make_task(task_id="deep_a", estimated_duration_min=60, required_focus_level="deep"),
            make_task(
                task_id="read_b", estimated_duration_min=90, category="concept_review"
            ),
            make_task(task_id="prac_c", estimated_duration_min=60, dependencies=["deep_a"]),
            make_task(task_id="rev_d", estimated_duration_min=30, category="review"),
        )
        policy = DEEP_WORK_POLICY.model_copy(
            update={
                "prefer_evening_sessions": True,
                "avoid_back_to_back_deep_work": True,
            }
        )
        inp = make_input(
            plan,
            policy=policy,
            free_busy=[busy(MONDAY.replace(hour=10), minutes=90)],
            horizon_days=7,
        )
        return plan, inp

    _, inp_one = build()
    _, inp_two = build()
    assert schedule(inp_one).model_dump_json() == schedule(inp_two).model_dump_json()


# --------------------------------------------------------------------------- #
# score_schedule — schedule-level totals (the report / polish objective)
# --------------------------------------------------------------------------- #


def test_score_schedule_zero_cost_day() -> None:
    """Two tasks on one day, buffered and target-fitting → every total 0."""
    plan = make_plan(
        make_task(task_id="a", estimated_duration_min=60),
        make_task(task_id="b", estimated_duration_min=60),
    )
    inp = make_input(plan, horizon_days=1)
    out = schedule(inp)
    breakdown = score_schedule(out, inp)
    assert out.scheduled_tasks[0].start == MONDAY.replace(hour=8)
    assert out.scheduled_tasks[1].start == MONDAY.replace(hour=10)  # buffered
    assert breakdown.target_daily_min == 120
    assert breakdown.daily_balance_total == 0
    assert breakdown.back_to_back_total == 0
    assert breakdown.fragmentation_total == 0
    assert breakdown.earliness_total == 0
    assert breakdown.total_cost == 0
    assert breakdown.per_day_minutes == {"2026-05-04": 120}
    assert breakdown.band_histogram == {"morning": 2}
    assert (breakdown.scheduled_count, breakdown.unscheduled_count) == (2, 0)


def test_score_schedule_totals_on_a_stacked_schedule() -> None:
    """Hand-checked totals for the zero-weight stacking of the acceptance
    fixture: Mon 08/09/10/11 + Tue 08 → daily overflow 140, three adjacent
    Mon pairs at gap 0 → 45, no slivers, one block a day past horizon
    start → earliness 1."""
    plan = make_plan(
        *[make_task(task_id=f"t_{i}", estimated_duration_min=60) for i in range(5)]
    )
    inp = make_input(plan, horizon_days=3)
    stacked = schedule(inp, scoring=ZERO_WEIGHTS)
    breakdown = score_schedule(stacked, inp)
    assert breakdown.target_daily_min == 100
    assert breakdown.per_day_minutes == {"2026-05-04": 240, "2026-05-05": 60}
    assert breakdown.daily_balance_total == 140
    assert breakdown.back_to_back_total == 45
    assert breakdown.fragmentation_total == 0
    assert breakdown.earliness_total == 1
    assert breakdown.total_cost == 3 * 140 + 2 * 45 + 1 * 1


def test_score_schedule_deep_conservation_and_pair_doubling() -> None:
    """Non-deep minutes inside deep windows count; adjacent deep pairs double
    only under ``avoid_back_to_back_deep_work``."""
    from agentic_calendar.contracts.scheduler_output import (
        CalendarEventStatus,
        ScheduledTask,
        SchedulerOutput,
        ScheduleStatus,
    )

    plan = make_plan(
        make_task(task_id="d1", estimated_duration_min=60, required_focus_level="deep"),
        make_task(task_id="d2", estimated_duration_min=60, required_focus_level="deep"),
        make_task(task_id="shallow", estimated_duration_min=60),
    )
    avoid = DEEP_WORK_POLICY.model_copy(
        update={"avoid_back_to_back_deep_work": True}
    )
    inp = make_input(plan, policy=avoid, horizon_days=2)
    monday_deep = MONDAY.replace(hour=18)  # Mon deep window 18:00-21:00

    def placed(task_id: str, start: datetime) -> ScheduledTask:
        return ScheduledTask(
            task_id=task_id,
            start=start,
            end=start + timedelta(minutes=60),
            calendar_event_status=CalendarEventStatus.DRAFT_ONLY,
        )

    output = SchedulerOutput(
        run_id=inp.run_id,
        plan_version=inp.plan_version,
        schedule_status=ScheduleStatus.SUCCESS,
        scheduled_tasks=[
            placed("d1", monday_deep),
            placed("d2", monday_deep + timedelta(minutes=60)),  # gap 0, both deep
            placed("shallow", monday_deep + timedelta(minutes=120)),  # in deep window
        ],
        unscheduled_tasks=[],
        available_capacity_min=0,
        largest_available_block_min=0,
        repair_options=[],
    )
    breakdown = score_schedule(output, inp)
    # d1→d2 doubles (15 x 2); d2→shallow is a plain adjacency (15).
    assert breakdown.back_to_back_total == 30 + 15
    # The shallow hour sits entirely inside Monday's deep window.
    assert breakdown.deep_window_conservation_total == 60
