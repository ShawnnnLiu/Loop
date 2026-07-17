"""End-to-end tests for ``scheduler.schedule``.

We exercise every ``ReasonCode`` the Phase 1 scheduler emits and assert on
the structured ``debug`` payloads. No prompt wording is involved.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from agentic_calendar.contracts.reason_codes import ReasonCode
from agentic_calendar.contracts.scheduler_output import (
    CalendarEventStatus,
    RepairOption,
    ScheduleStatus,
)
from agentic_calendar.scheduler import schedule
from agentic_calendar.scheduler.scoring import PlacementScoringConfig
from tests.scheduler._helpers import (
    DEEP_WORK_POLICY,
    DEFAULT_POLICY,
    ZERO_WEIGHTS,
    busy,
    make_input,
    make_plan,
    make_task,
)


def test_simple_two_task_chain_succeeds() -> None:
    plan = make_plan(
        make_task(task_id="a", estimated_duration_min=60),
        make_task(task_id="b", estimated_duration_min=60, dependencies=["a"]),
    )
    out = schedule(make_input(plan))
    assert out.schedule_status is ScheduleStatus.SUCCESS
    assert [t.task_id for t in out.scheduled_tasks] == ["a", "b"]
    for st in out.scheduled_tasks:
        assert st.calendar_event_status is CalendarEventStatus.DRAFT_ONLY
    assert out.scheduled_tasks[0].end <= out.scheduled_tasks[1].start


def test_dependency_blocked_when_dep_not_complete_and_dep_missing() -> None:
    """A task whose dependency is not in completion set yields dependency-blocked.

    We construct a plan where ``b`` depends on ``a``; ``a`` is removed by
    using ``model_construct`` so ``b``'s dep cannot be satisfied at runtime.
    """
    from agentic_calendar.contracts.common_types import FocusLevel, TaskCategory
    from agentic_calendar.contracts.task_plan import Task, TaskPlan

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
    out = schedule(make_input(plan))
    assert out.schedule_status is ScheduleStatus.FAILED
    assert len(out.unscheduled_tasks) == 1
    u = out.unscheduled_tasks[0]
    assert u.reason_code is ReasonCode.DEPENDENCY_BLOCKED
    assert u.debug["blocked_by"] == ["missing_a"]


def test_task_too_long_unsplittable_emitted() -> None:
    plan = make_plan(
        make_task(
            task_id="huge",
            estimated_duration_min=DEFAULT_POLICY.max_session_length_min + 30,
            splittable=False,
        )
    )
    out = schedule(make_input(plan))
    assert out.schedule_status is ScheduleStatus.FAILED
    u = out.unscheduled_tasks[0]
    assert u.reason_code is ReasonCode.TASK_TOO_LONG_UNSPLITTABLE
    assert u.debug["duration_min"] == DEFAULT_POLICY.max_session_length_min + 30
    assert u.debug["max_session_length_min"] == DEFAULT_POLICY.max_session_length_min


def test_no_valid_contiguous_block_when_no_window_fits() -> None:
    """A 90-minute task with capacity but no 90-minute contiguous slot.

    Two 60-minute free windows over two days give 120 min capacity (more
    than the 90-min task) but no single 90-min contiguous block. The
    capacity-promotion path therefore must NOT fire — the failure stays
    typed as ``NO_VALID_CONTIGUOUS_BLOCK`` (golden scenario 15).
    """
    plan = make_plan(
        make_task(task_id="x", estimated_duration_min=90, splittable=True)
    )
    horizon_start = datetime(2026, 5, 4, 0, 0, 0, tzinfo=UTC)
    quiet_only = DEFAULT_POLICY.model_copy(
        update={"no_events_before": "20:00", "no_events_after": "21:00"}
    )
    out = schedule(
        make_input(plan, policy=quiet_only, horizon_days=2, horizon_start=horizon_start)
    )
    assert out.schedule_status is ScheduleStatus.FAILED
    u = out.unscheduled_tasks[0]
    assert u.reason_code is ReasonCode.NO_VALID_CONTIGUOUS_BLOCK
    assert u.debug["required_duration_min"] == 90
    assert u.debug["largest_available_block_min"] == 60
    assert "rejected_windows" in u.debug
    assert u.debug["suggested_repair"] == RepairOption.SPLIT_TASK.value


def test_deep_work_required_unavailable() -> None:
    """A deep-focus task with no deep-work window in the horizon at all."""
    plan = make_plan(
        make_task(
            task_id="deep",
            estimated_duration_min=60,
            required_focus_level="deep",
        )
    )
    no_deep_windows = DEEP_WORK_POLICY.model_copy(update={"deep_work_windows": []})
    out = schedule(make_input(plan, policy=no_deep_windows, horizon_days=1))
    assert out.schedule_status is ScheduleStatus.FAILED
    u = out.unscheduled_tasks[0]
    assert u.reason_code is ReasonCode.DEEP_WORK_REQUIRED_UNAVAILABLE
    assert u.debug["required_focus_level"] == "deep"
    assert u.debug["deep_work_windows_seen"] == 0


def test_deep_work_task_placed_in_deep_window() -> None:
    plan = make_plan(
        make_task(
            task_id="deep",
            estimated_duration_min=60,
            required_focus_level="deep",
        )
    )
    horizon_start = datetime(2026, 5, 4, 0, 0, 0, tzinfo=UTC)
    out = schedule(make_input(plan, policy=DEEP_WORK_POLICY, horizon_days=2,
                              horizon_start=horizon_start))
    assert out.schedule_status is ScheduleStatus.SUCCESS
    placement = out.scheduled_tasks[0]
    expected_start = datetime(2026, 5, 4, 18, 0, 0, tzinfo=UTC)  # Mon 18:00 UTC
    assert placement.start == expected_start


def test_regret_order_places_the_stranded_deep_task() -> None:
    """Insertion order (axiom 05): the single-candidate 120-min deep task
    places before the flexible 60-min deep task, so both fit. Under the old
    first-come order, ``a_flex`` (earlier sort key) took Monday's deep
    window first and stranded ``b_long`` — its only feasible slot."""
    from agentic_calendar.scheduler.policy import DeepWorkWindowPolicy

    policy = DEEP_WORK_POLICY.model_copy(
        update={
            "deep_work_windows": [
                DeepWorkWindowPolicy(day="Mon", start="18:00", end="20:00"),
                DeepWorkWindowPolicy(day="Tue", start="18:00", end="19:00"),
            ]
        }
    )
    plan = make_plan(
        make_task(
            task_id="a_flex", estimated_duration_min=60, required_focus_level="deep"
        ),
        make_task(
            task_id="b_long", estimated_duration_min=120, required_focus_level="deep"
        ),
    )
    horizon_start = datetime(2026, 5, 4, 0, 0, 0, tzinfo=UTC)  # Mon
    out = schedule(
        make_input(plan, policy=policy, horizon_days=7, horizon_start=horizon_start)
    )
    assert out.schedule_status is ScheduleStatus.SUCCESS
    starts = {st.task_id: st.start for st in out.scheduled_tasks}
    assert starts == {
        "b_long": datetime(2026, 5, 4, 18, 0, 0, tzinfo=UTC),  # its only slot
        "a_flex": datetime(2026, 5, 5, 18, 0, 0, tzinfo=UTC),
    }
    # Output ordering stays topological (a_flex first), not placement round.
    assert [st.task_id for st in out.scheduled_tasks] == ["a_flex", "b_long"]


def test_crunch_week_failures_identical_to_zero_weight_baseline() -> None:
    """Soft quotas never eliminate feasibility (axiom 05): in a crunch week
    (load > capacity) the default weights fail exactly the same tasks as
    the zero-weight baseline, and the capacity promotion still fires."""
    plan = make_plan(
        *[
            make_task(task_id=f"t{i}", estimated_duration_min=120, splittable=True)
            for i in range(4)  # 480 min required
        ]
    )
    crunch = DEFAULT_POLICY.model_copy(
        update={"no_events_before": "20:00", "no_events_after": "21:00"}
    )
    inp = make_input(plan, policy=crunch, horizon_days=3)  # 180 min capacity
    default_out = schedule(inp)
    baseline_out = schedule(inp, scoring=ZERO_WEIGHTS)
    assert [(u.task_id, u.reason_code) for u in default_out.unscheduled_tasks] == [
        (u.task_id, u.reason_code) for u in baseline_out.unscheduled_tasks
    ]
    assert default_out.unscheduled_tasks, "crunch fixture must fail tasks"
    assert all(
        u.reason_code is ReasonCode.INSUFFICIENT_WEEKLY_CAPACITY
        for u in default_out.unscheduled_tasks
    )


def test_partial_failure_when_some_tasks_fit_others_dont() -> None:
    plan = make_plan(
        make_task(task_id="ok", estimated_duration_min=60),
        make_task(
            task_id="too_big",
            estimated_duration_min=DEFAULT_POLICY.max_session_length_min + 60,
            splittable=False,
        ),
    )
    out = schedule(make_input(plan))
    assert out.schedule_status is ScheduleStatus.PARTIAL_FAILURE
    assert len(out.scheduled_tasks) == 1
    assert len(out.unscheduled_tasks) == 1
    assert out.repair_options  # non-empty per axiom 05


def test_busy_intervals_are_avoided() -> None:
    plan = make_plan(make_task(task_id="t1", estimated_duration_min=60))
    horizon_start = datetime(2026, 5, 4, 0, 0, 0, tzinfo=UTC)
    block = busy(datetime(2026, 5, 4, 8, 0, 0, tzinfo=UTC), minutes=60)
    out = schedule(
        make_input(
            plan,
            free_busy=[block],
            horizon_start=horizon_start,
            horizon_days=1,
        )
    )
    assert out.schedule_status is ScheduleStatus.SUCCESS
    placement = out.scheduled_tasks[0]
    assert placement.start >= datetime(2026, 5, 4, 9, 0, 0, tzinfo=UTC)


def test_max_daily_study_capped() -> None:
    plan = make_plan(
        *[
            make_task(task_id=f"t_{i}", estimated_duration_min=60)
            for i in range(6)
        ]
    )
    capped = DEFAULT_POLICY.model_copy(update={"max_daily_study_min": 120})
    out = schedule(make_input(plan, policy=capped, horizon_days=2))
    daily: dict[str, int] = {}
    for st in out.scheduled_tasks:
        key = st.start.date().isoformat()
        daily[key] = daily.get(key, 0) + 60
    assert all(v <= 120 for v in daily.values())


def test_repair_options_non_empty_on_failure() -> None:
    plan = make_plan(
        make_task(
            task_id="huge",
            estimated_duration_min=999,
            splittable=False,
        )
    )
    out = schedule(make_input(plan))
    assert out.schedule_status is ScheduleStatus.FAILED
    assert RepairOption.EXTEND_TIMELINE in out.repair_options


def test_completed_dependency_unlocks_task() -> None:
    """Isolated: 'b' depends on 'a', which is NOT in the plan at all.

    Only completed_task_ids can satisfy the dependency here, so this proves
    the unlock comes from the completion marker — not from 'a' being placed
    earlier in the same run.
    """
    plan = make_plan(make_task(task_id="b", dependencies=["a"]))

    blocked = schedule(make_input(plan))
    assert blocked.schedule_status is ScheduleStatus.FAILED
    assert blocked.unscheduled_tasks[0].reason_code is ReasonCode.DEPENDENCY_BLOCKED
    assert blocked.unscheduled_tasks[0].debug["blocked_by"] == ["a"]

    unlocked = schedule(make_input(plan, completed_task_ids=["a"]))
    assert unlocked.schedule_status is ScheduleStatus.SUCCESS
    assert [st.task_id for st in unlocked.scheduled_tasks] == ["b"]


def test_completed_tasks_in_plan_are_still_placed() -> None:
    """Documented MVP behavior: completed_task_ids satisfies the dependency
    relation only — it does NOT suppress placement of a task that is still in
    the plan. The Planner is responsible for dropping done tasks from the
    plan; if that division of labor changes, this test must change with it.
    """
    plan = make_plan(
        make_task(task_id="a"),
        make_task(task_id="b", dependencies=["a"]),
    )
    out = schedule(make_input(plan, completed_task_ids=["a"]))
    assert out.schedule_status is ScheduleStatus.SUCCESS
    assert {st.task_id for st in out.scheduled_tasks} == {"a", "b"}


@pytest.mark.parametrize(
    "scoring", [None, ZERO_WEIGHTS], ids=["default_weights", "zero_weights"]
)
def test_dependent_fails_typed_instead_of_starting_before_dependency_ends(
    scoring: PlacementScoringConfig | None,
) -> None:
    """Dependency temporal floor: the inversion repro now fails typed.

    Free windows on Mon 2026-05-04 under DEFAULT_POLICY hours (08:00-22:30):
    09:00-10:00 (60 min) and 18:00-20:00 (120 min). ``dep`` (120 min) fits
    only the evening window; ``child`` (60 min, depends on ``dep``) then has
    exactly one remaining slot — the 09:00 morning window, before its
    dependency even starts. Pre-floor, the greedy loop silently placed the
    inverted pair and reported SUCCESS (axiom 05 hard-rule violation,
    recorded in commit 2c00064). The floor discards the morning candidate,
    so ``child`` fails ``NO_VALID_CONTIGUOUS_BLOCK`` with the fully-floored
    window marked ``before_dependency_end``. Both tasks are
    single-candidate, so the scenario is weight-independent (parametrized to
    prove it).
    """
    plan = make_plan(
        make_task(task_id="dep", estimated_duration_min=120),
        make_task(task_id="child", estimated_duration_min=60, dependencies=["dep"]),
    )
    free_busy = [
        busy(datetime(2026, 5, 4, 8, 0, tzinfo=UTC), minutes=60),  # 08:00-09:00
        busy(datetime(2026, 5, 4, 10, 0, tzinfo=UTC), minutes=480),  # 10:00-18:00
        busy(datetime(2026, 5, 4, 20, 0, tzinfo=UTC), minutes=150),  # 20:00-22:30
    ]
    out = schedule(
        make_input(
            plan,
            free_busy=free_busy,
            horizon_days=1,
            horizon_start=datetime(2026, 5, 4, 0, 0, 0, tzinfo=UTC),
        ),
        scoring=scoring,
    )
    assert out.schedule_status is ScheduleStatus.PARTIAL_FAILURE
    placed = {st.task_id: st for st in out.scheduled_tasks}
    assert set(placed) == {"dep"}
    assert placed["dep"].start == datetime(2026, 5, 4, 18, 0, tzinfo=UTC)
    (unsched,) = out.unscheduled_tasks
    assert unsched.task_id == "child"
    assert unsched.reason_code is ReasonCode.NO_VALID_CONTIGUOUS_BLOCK
    reasons = {
        w["rejection_reason"] for w in unsched.debug["rejected_windows"]
    }
    assert reasons == {"before_dependency_end"}


@pytest.mark.parametrize(
    "scoring", [None, ZERO_WEIGHTS], ids=["default_weights", "zero_weights"]
)
def test_dependency_floor_shifts_dependent_to_post_dependency_slot(
    scoring: PlacementScoringConfig | None,
) -> None:
    """Same shape plus a 20:30-21:30 window: instead of failing, ``child``
    lands in the first slot after its dependency ends. The morning slot
    (which earliest-feasible placement would otherwise pick under
    ZERO_WEIGHTS) is discarded by the floor, not by feasibility."""
    plan = make_plan(
        make_task(task_id="dep", estimated_duration_min=120),
        make_task(task_id="child", estimated_duration_min=60, dependencies=["dep"]),
    )
    free_busy = [
        busy(datetime(2026, 5, 4, 8, 0, tzinfo=UTC), minutes=60),  # 08:00-09:00
        busy(datetime(2026, 5, 4, 10, 0, tzinfo=UTC), minutes=480),  # 10:00-18:00
        busy(datetime(2026, 5, 4, 20, 0, tzinfo=UTC), minutes=30),  # 20:00-20:30
        busy(datetime(2026, 5, 4, 21, 30, tzinfo=UTC), minutes=150),  # 21:30-24:00
    ]
    out = schedule(
        make_input(
            plan,
            free_busy=free_busy,
            horizon_days=1,
            horizon_start=datetime(2026, 5, 4, 0, 0, 0, tzinfo=UTC),
        ),
        scoring=scoring,
    )
    assert out.schedule_status is ScheduleStatus.SUCCESS
    placed = {st.task_id: st for st in out.scheduled_tasks}
    assert placed["dep"].start == datetime(2026, 5, 4, 18, 0, tzinfo=UTC)
    assert placed["child"].start == datetime(2026, 5, 4, 20, 30, tzinfo=UTC)
    assert placed["child"].start >= placed["dep"].end
