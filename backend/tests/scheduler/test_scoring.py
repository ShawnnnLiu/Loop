"""Scored-placement machinery tests (axiom 05 "Scored Placement").

The load-bearing test is the first-fit equivalence proof: with
window-start-only candidates and cost ≡ 0, the scored path must produce
byte-identical ``SchedulerOutput`` to the original first-fit ``_try_place``
across every greedy/golden scheduler scenario. ``_first_fit_reference`` is
a verbatim copy of the pre-refactor ``_try_place`` body and lives only in
this test module; it is deleted when the scoring terms land (P-C) and the
equivalence deliberately stops holding.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest

from agentic_calendar.contracts.common_types import FocusLevel, TaskCategory
from agentic_calendar.contracts.task_plan import Task, TaskPlan
from agentic_calendar.scheduler import greedy, schedule
from agentic_calendar.scheduler.greedy import _Placement
from agentic_calendar.scheduler.inputs import FreeBusyInterval, SchedulerInput
from agentic_calendar.scheduler.policy import DeepWorkWindowPolicy, SchedulingPolicy
from agentic_calendar.scheduler.scoring import (
    PlacementCandidate,
    PlacementState,
    _live_windows,
    day_key,
    enumerate_candidates,
    select_placement,
)
from agentic_calendar.scheduler.windows import FreeWindow
from tests.scheduler._helpers import (
    DEEP_WORK_POLICY,
    DEFAULT_POLICY,
    busy,
    make_input,
    make_plan,
    make_task,
)

# --------------------------------------------------------------------------- #
# First-fit reference (verbatim pre-refactor ``_try_place`` body)
# --------------------------------------------------------------------------- #


def _first_fit_reference(
    task: Task,
    windows: list[FreeWindow],
    inp: SchedulerInput,
    state: PlacementState,
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
        key = day_key(candidate_start)
        used_today = state.minutes_per_day.get(key, 0)
        if used_today + duration > inp.policy.max_daily_study_min:
            continue
        if needs_deep:
            last = state.last_deep_end.get(key)
            if last is not None:
                gap = (candidate_start - last).total_seconds() / 60
                if gap < inp.policy.min_break_between_deep_blocks_min:
                    continue
        return _Placement(
            start=candidate_start, end=candidate_end, window_was_deep=window.is_deep_work
        )
    return None


# --------------------------------------------------------------------------- #
# Scenario builders — every ``schedule()`` input exercised by
# ``tests/scheduler/test_greedy.py`` and
# ``tests/golden/test_scheduler_scenarios.py``, plus a deep-gap case.
# --------------------------------------------------------------------------- #

HORIZON_START = datetime(2026, 5, 4, 0, 0, 0, tzinfo=UTC)  # Mon


def _case_two_task_chain() -> SchedulerInput:
    plan = make_plan(
        make_task(task_id="a", estimated_duration_min=60),
        make_task(task_id="b", estimated_duration_min=60, dependencies=["a"]),
    )
    return make_input(plan)


def _case_missing_dependency() -> SchedulerInput:
    b = Task.model_construct(
        task_id="b",
        module_id="dp",
        title="b",
        description="",
        dependencies=["missing_a"],
        estimated_duration_min=60,
        cognitive_load=3,
        category=TaskCategory.PRACTICE,
        required_focus_level=FocusLevel.MEDIUM,
        splittable=False,
    )
    plan = TaskPlan.model_construct(plan_version="p", tasks=[b])
    return make_input(plan)


def _case_task_too_long_unsplittable() -> SchedulerInput:
    plan = make_plan(
        make_task(
            task_id="huge",
            estimated_duration_min=DEFAULT_POLICY.max_session_length_min + 30,
            splittable=False,
        )
    )
    return make_input(plan)


def _case_fragmented_short_windows() -> SchedulerInput:
    plan = make_plan(make_task(task_id="x", estimated_duration_min=90, splittable=True))
    quiet_only = DEFAULT_POLICY.model_copy(
        update={"no_events_before": "20:00", "no_events_after": "21:00"}
    )
    return make_input(plan, policy=quiet_only, horizon_days=2, horizon_start=HORIZON_START)


def _case_deep_required_no_deep_windows() -> SchedulerInput:
    plan = make_plan(
        make_task(task_id="deep", estimated_duration_min=60, required_focus_level="deep")
    )
    no_deep_windows = DEEP_WORK_POLICY.model_copy(update={"deep_work_windows": []})
    return make_input(plan, policy=no_deep_windows, horizon_days=1)


def _case_deep_task_in_deep_window() -> SchedulerInput:
    plan = make_plan(
        make_task(task_id="deep", estimated_duration_min=60, required_focus_level="deep")
    )
    return make_input(
        plan, policy=DEEP_WORK_POLICY, horizon_days=2, horizon_start=HORIZON_START
    )


def _case_two_deep_tasks_break_gap() -> SchedulerInput:
    """Second deep task must skip the same-day remainder (deep-gap check)."""
    plan = make_plan(
        make_task(task_id="deep_1", estimated_duration_min=60, required_focus_level="deep"),
        make_task(task_id="deep_2", estimated_duration_min=60, required_focus_level="deep"),
    )
    return make_input(
        plan, policy=DEEP_WORK_POLICY, horizon_days=2, horizon_start=HORIZON_START
    )


def _case_partial_failure_mixed() -> SchedulerInput:
    plan = make_plan(
        make_task(task_id="ok", estimated_duration_min=60),
        make_task(
            task_id="too_big",
            estimated_duration_min=DEFAULT_POLICY.max_session_length_min + 60,
            splittable=False,
        ),
    )
    return make_input(plan)


def _case_busy_interval_avoided() -> SchedulerInput:
    plan = make_plan(make_task(task_id="t1", estimated_duration_min=60))
    block = busy(datetime(2026, 5, 4, 8, 0, 0, tzinfo=UTC), minutes=60)
    return make_input(
        plan, free_busy=[block], horizon_start=HORIZON_START, horizon_days=1
    )


def _case_daily_cap_spills_over() -> SchedulerInput:
    plan = make_plan(
        *[make_task(task_id=f"t_{i}", estimated_duration_min=60) for i in range(6)]
    )
    capped = DEFAULT_POLICY.model_copy(update={"max_daily_study_min": 120})
    return make_input(plan, policy=capped, horizon_days=2)


def _case_unsplittable_999() -> SchedulerInput:
    plan = make_plan(make_task(task_id="huge", estimated_duration_min=999, splittable=False))
    return make_input(plan)


def _case_dependency_needs_completion() -> SchedulerInput:
    plan = make_plan(make_task(task_id="b", dependencies=["a"]))
    return make_input(plan)


def _case_dependency_unlocked_by_completion() -> SchedulerInput:
    plan = make_plan(make_task(task_id="b", dependencies=["a"]))
    return make_input(plan, completed_task_ids=["a"])


def _case_completed_task_still_in_plan() -> SchedulerInput:
    plan = make_plan(
        make_task(task_id="a"),
        make_task(task_id="b", dependencies=["a"]),
    )
    return make_input(plan, completed_task_ids=["a"])


def _case_golden_limited_capacity() -> SchedulerInput:
    plan = make_plan(
        *[
            make_task(task_id=f"t{i}", estimated_duration_min=120, splittable=True)
            for i in range(4)
        ],
        plan_version="p_capacity",
    )
    capped_policy = DEFAULT_POLICY.model_copy(
        update={"no_events_before": "20:00", "no_events_after": "21:00"}
    )
    return make_input(
        plan, policy=capped_policy, horizon_days=3, horizon_start=HORIZON_START
    )


def _case_golden_weekend_only() -> SchedulerInput:
    weekend_friendly = SchedulingPolicy(
        no_events_before="08:00",
        no_events_after="22:30",
        allow_weekends=True,
        min_break_between_deep_blocks_min=30,
        max_daily_study_min=240,
        respect_deep_work_windows=True,
        deep_work_windows=[DeepWorkWindowPolicy(day="Sat", start="09:00", end="13:00")],
        max_session_length_min=120,
        preferred_session_length_min=60,
    )
    plan = make_plan(
        make_task(task_id="deep_one", estimated_duration_min=90, required_focus_level="deep"),
        plan_version="p_weekend",
    )
    weekday_busy = [
        FreeBusyInterval(
            start=HORIZON_START + timedelta(days=d, hours=8),
            end=HORIZON_START + timedelta(days=d, hours=22, minutes=30),
        )
        for d in range(5)  # Mon-Fri fully busy
    ]
    return make_input(
        plan,
        policy=weekend_friendly,
        free_busy=weekday_busy,
        horizon_days=7,
        horizon_start=HORIZON_START,
    )


def _case_golden_timeline_infeasible() -> SchedulerInput:
    plan = make_plan(
        *[
            make_task(task_id=f"t{i}", estimated_duration_min=60, splittable=True)
            for i in range(20)
        ],
        plan_version="p_timeline",
    )
    return make_input(plan, horizon_days=1, horizon_start=HORIZON_START)


def _case_golden_success_single() -> SchedulerInput:
    plan = make_plan(make_task(task_id="t1", estimated_duration_min=60), plan_version="p_ok")
    return make_input(plan, horizon_days=7, horizon_start=HORIZON_START)


CASES: list[tuple[str, Callable[[], SchedulerInput]]] = [
    ("two_task_chain", _case_two_task_chain),
    ("missing_dependency", _case_missing_dependency),
    ("task_too_long_unsplittable", _case_task_too_long_unsplittable),
    ("fragmented_short_windows", _case_fragmented_short_windows),
    ("deep_required_no_deep_windows", _case_deep_required_no_deep_windows),
    ("deep_task_in_deep_window", _case_deep_task_in_deep_window),
    ("two_deep_tasks_break_gap", _case_two_deep_tasks_break_gap),
    ("partial_failure_mixed", _case_partial_failure_mixed),
    ("busy_interval_avoided", _case_busy_interval_avoided),
    ("daily_cap_spills_over", _case_daily_cap_spills_over),
    ("unsplittable_999", _case_unsplittable_999),
    ("dependency_needs_completion", _case_dependency_needs_completion),
    ("dependency_unlocked_by_completion", _case_dependency_unlocked_by_completion),
    ("completed_task_still_in_plan", _case_completed_task_still_in_plan),
    ("golden_limited_capacity", _case_golden_limited_capacity),
    ("golden_weekend_only", _case_golden_weekend_only),
    ("golden_timeline_infeasible", _case_golden_timeline_infeasible),
    ("golden_success_single", _case_golden_success_single),
]


@pytest.mark.parametrize(("name", "build"), CASES, ids=[name for name, _ in CASES])
def test_scored_path_is_output_identical_to_first_fit(
    name: str,
    build: Callable[[], SchedulerInput],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """P-B equivalence proof: old and new placement paths agree byte-for-byte."""
    del name
    inp = build()
    scored = schedule(inp)
    monkeypatch.setattr(greedy, "_try_place", _first_fit_reference)
    first_fit = schedule(inp)
    assert scored.model_dump() == first_fit.model_dump()
    assert scored.model_dump_json() == first_fit.model_dump_json()


# --------------------------------------------------------------------------- #
# Unit tests for the candidate machinery
# --------------------------------------------------------------------------- #


def _window(start: datetime, minutes: int, *, deep: bool = False) -> FreeWindow:
    return FreeWindow(start=start, end=start + timedelta(minutes=minutes), is_deep_work=deep)


def _fresh_state() -> PlacementState:
    return PlacementState(busy=[], minutes_per_day={}, last_deep_end={})


def test_select_placement_empty_returns_none() -> None:
    assert select_placement([]) is None


def test_select_placement_breaks_cost_ties_by_earliest_start() -> None:
    early = _window(datetime(2026, 5, 4, 9, 0, tzinfo=UTC), 60)
    late = _window(datetime(2026, 5, 4, 12, 0, tzinfo=UTC), 60)
    candidates = [
        PlacementCandidate(start=late.start, end=late.end, window=late),
        PlacementCandidate(start=early.start, end=early.end, window=early),
    ]
    chosen = select_placement(candidates)
    assert chosen is not None
    assert chosen.start == early.start


def test_enumerate_candidates_returns_every_feasible_window_start() -> None:
    """All feasible windows yield a candidate (not just the first), starts only."""
    task = Task.model_validate(make_task(task_id="t", estimated_duration_min=60))
    w_short = _window(datetime(2026, 5, 4, 8, 0, tzinfo=UTC), 30)  # too small
    w_fit_1 = _window(datetime(2026, 5, 4, 9, 0, tzinfo=UTC), 90)
    w_fit_2 = _window(datetime(2026, 5, 5, 9, 0, tzinfo=UTC), 60)
    candidates = enumerate_candidates(
        task, [w_short, w_fit_1, w_fit_2], _fresh_state(), DEFAULT_POLICY
    )
    assert [(c.start, c.window) for c in candidates] == [
        (w_fit_1.start, w_fit_1),
        (w_fit_2.start, w_fit_2),
    ]
    assert all(c.end - c.start == timedelta(minutes=60) for c in candidates)


def test_enumerate_candidates_applies_daily_cap_and_deep_gap() -> None:
    """The daily-cap and break-between-deep-blocks hard checks filter candidates."""
    deep_policy = DEEP_WORK_POLICY.model_copy(update={"max_daily_study_min": 120})
    task = Task.model_validate(
        make_task(task_id="d", estimated_duration_min=60, required_focus_level="deep")
    )
    monday_deep = _window(datetime(2026, 5, 4, 19, 0, tzinfo=UTC), 120, deep=True)
    tuesday_deep = _window(datetime(2026, 5, 5, 18, 0, tzinfo=UTC), 120, deep=True)
    state = PlacementState(
        busy=[],
        minutes_per_day={"2026-05-04": 60},
        last_deep_end={"2026-05-04": datetime(2026, 5, 4, 19, 0, tzinfo=UTC)},
    )
    # Monday start 19:00 passes the cap (60+60 <= 120) but fails the deep gap
    # (0 < 30 min since the last deep end); Tuesday remains feasible.
    candidates = enumerate_candidates(task, [monday_deep, tuesday_deep], state, deep_policy)
    assert [c.start for c in candidates] == [tuesday_deep.start]

    over_cap = PlacementState(
        busy=[], minutes_per_day={"2026-05-04": 90}, last_deep_end={}
    )
    candidates = enumerate_candidates(task, [monday_deep, tuesday_deep], over_cap, deep_policy)
    assert [c.start for c in candidates] == [tuesday_deep.start]
