"""Bounded polish pass (axiom 05 "Bounded polish pass").

The pass relocates placed blocks under the schedule-level objective
(``score_blocks``, the ``score_schedule`` engine) — strict integer
improvement, at most two sweeps, moves only. These tests pin the greedy
artifact it exists to fix, the feasibility rules (dependency order both
directions, pairwise deep gaps), determinism/idempotence, and that the
failure surface is untouched while polish is active.
"""

from __future__ import annotations

from datetime import UTC, datetime

from agentic_calendar.contracts.reason_codes import ReasonCode
from agentic_calendar.contracts.scheduler_output import (
    CalendarEventStatus,
    ScheduledTask,
    ScheduleStatus,
)
from agentic_calendar.scheduler import schedule
from agentic_calendar.scheduler.policy import DeepWorkWindowPolicy
from agentic_calendar.scheduler.polish import polish_placements
from agentic_calendar.scheduler.scoring import DEFAULT_PLACEMENT_SCORING_CONFIG
from tests.scheduler._helpers import (
    DEEP_WORK_POLICY,
    DEFAULT_POLICY,
    busy,
    make_input,
    make_plan,
    make_task,
)


def _dt(day: int, hour: int, minute: int = 0) -> datetime:
    """2026-05-04 (a Monday) + ``day`` days, at local ``hour:minute``."""
    return datetime(2026, 5, 4 + day, hour, minute, tzinfo=UTC)


def _placed(task_id: str, start: datetime, end: datetime) -> ScheduledTask:
    return ScheduledTask(
        task_id=task_id,
        start=start,
        end=end,
        calendar_event_status=CalendarEventStatus.DRAFT_ONLY,
    )


def _sliver_input(*extra_tasks: dict) -> object:
    """The greedy-artifact scenario: a 45-min busy-bounded chunk on day 1.

    Day 1 free: only 10:00-10:45. Day 2 free: 09:00-10:30. Greedy's
    *marginal* fragmentation penalizes the 30-min task inside the 45-min
    chunk (it strands a 15-min sliver) more than a clean day-2 start costs
    in earliness — but at the schedule level, leaving the whole 45-min
    chunk empty is the larger fragmentation. Polish must move the block
    into the chunk; the known optimum is day 1, 10:00-10:30.
    """
    plan = make_plan(
        make_task(task_id="t_small", estimated_duration_min=30),
        *extra_tasks,
    )
    return make_input(
        plan,
        free_busy=[
            busy(_dt(0, 8), minutes=120),  # 08:00-10:00
            busy(_dt(0, 10, 45), minutes=705),  # 10:45-22:30
            busy(_dt(1, 8), minutes=60),  # 08:00-09:00
            busy(_dt(1, 10, 30), minutes=720),  # 10:30-22:30
        ],
        horizon_days=2,
    )


def test_schedule_fills_the_stranded_sliver() -> None:
    """End-to-end: the polished schedule lands on the known optimum."""
    out = schedule(_sliver_input())
    assert out.schedule_status is ScheduleStatus.SUCCESS
    placement = out.scheduled_tasks[0]
    assert placement.start == _dt(0, 10)
    assert placement.end == _dt(0, 10, 30)


def test_polish_moves_the_artifact_block() -> None:
    """Unit: fed the pre-polish greedy placement, polish relocates it."""
    inp = _sliver_input()
    artifact = [_placed("t_small", _dt(1, 9), _dt(1, 9, 30))]
    polished = polish_placements(artifact, inp, DEFAULT_PLACEMENT_SCORING_CONFIG)
    assert polished == [_placed("t_small", _dt(0, 10), _dt(0, 10, 30))]


def test_polish_is_deterministic() -> None:
    first = schedule(_sliver_input())
    second = schedule(_sliver_input())
    assert first.model_dump_json() == second.model_dump_json()


def test_polish_is_idempotent_at_the_fixed_point() -> None:
    """Re-polishing a polished schedule makes no move (axiom 05)."""
    inp = _sliver_input()
    out = schedule(inp)
    once = polish_placements(
        list(out.scheduled_tasks), inp, DEFAULT_PLACEMENT_SCORING_CONFIG
    )
    assert once == list(out.scheduled_tasks)
    twice = polish_placements(once, inp, DEFAULT_PLACEMENT_SCORING_CONFIG)
    assert twice == once


def test_polish_noop_on_already_good_schedule() -> None:
    """No strictly-improving move exists — every block stays put."""
    plan = make_plan(
        make_task(task_id="a", estimated_duration_min=60),
        make_task(task_id="b", estimated_duration_min=60, dependencies=["a"]),
    )
    inp = make_input(plan)
    out = schedule(inp)
    assert out.schedule_status is ScheduleStatus.SUCCESS
    polished = polish_placements(
        list(out.scheduled_tasks), inp, DEFAULT_PLACEMENT_SCORING_CONFIG
    )
    assert polished == list(out.scheduled_tasks)


def test_polish_failure_surface_untouched_while_moving_blocks() -> None:
    """Polish moved a block AND the typed failure is byte-for-byte intact.

    Moves only: polish never unschedules, never reschedules a failed task,
    never touches ``unscheduled_tasks`` (axiom 05) — asserted here on a run
    where polish demonstrably acted.
    """
    huge = make_task(
        task_id="huge",
        estimated_duration_min=999,
        splittable=False,
    )
    out = schedule(_sliver_input(huge))
    assert out.schedule_status is ScheduleStatus.PARTIAL_FAILURE
    # The block was moved by polish (same known optimum as the clean run).
    assert [st.task_id for st in out.scheduled_tasks] == ["t_small"]
    assert out.scheduled_tasks[0].start == _dt(0, 10)
    # The failure kept its typed reason_code and debug payload exactly.
    assert [u.task_id for u in out.unscheduled_tasks] == ["huge"]
    failure = out.unscheduled_tasks[0]
    assert failure.reason_code is ReasonCode.TASK_TOO_LONG_UNSPLITTABLE
    assert failure.debug["duration_min"] == 999
    assert failure.debug["max_session_length_min"] == (
        DEFAULT_POLICY.max_session_length_min
    )
    assert out.repair_options


# --------------------------------------------------------------------------- #
# Dependency order both directions (axiom 05 "Bounded polish pass")
# --------------------------------------------------------------------------- #

_TUE_ONLY_DEEP = DEEP_WORK_POLICY.model_copy(
    update={
        "deep_work_windows": [
            DeepWorkWindowPolicy(day="Tue", start="18:00", end="19:00")
        ]
    }
)


def _floor_case_input(*, with_dependency: bool) -> object:
    """Immovable deep parent Tue 18:00; child hand-placed Wed 09:00.

    Mon 09:00-10:00 is free and strictly improves the child's earliness —
    but it lies before the parent's end, so the dependency floor must
    forbid it. The no-dependency control proves the temptation is real.
    """
    plan = make_plan(
        make_task(
            task_id="p_parent",
            estimated_duration_min=60,
            required_focus_level="deep",
        ),
        make_task(
            task_id="c_child",
            estimated_duration_min=60,
            dependencies=["p_parent"] if with_dependency else [],
        ),
    )
    return make_input(
        plan,
        policy=_TUE_ONLY_DEEP,
        free_busy=[
            busy(_dt(0, 8), minutes=60),  # Mon 08:00-09:00
            busy(_dt(0, 10), minutes=750),  # Mon 10:00-22:30
            busy(_dt(1, 8), minutes=600),  # Tue 08:00-18:00
            busy(_dt(1, 19), minutes=210),  # Tue 19:00-22:30
            busy(_dt(2, 8), minutes=60),  # Wed 08:00-09:00
            busy(_dt(2, 10), minutes=750),  # Wed 10:00-22:30
        ],
        horizon_days=3,
    )


_FLOOR_CASE_PLACED = [
    _placed("p_parent", _dt(1, 18), _dt(1, 19)),
    _placed("c_child", _dt(2, 9), _dt(2, 10)),
]


def test_polish_respects_the_dependency_floor() -> None:
    inp = _floor_case_input(with_dependency=True)
    polished = polish_placements(
        list(_FLOOR_CASE_PLACED), inp, DEFAULT_PLACEMENT_SCORING_CONFIG
    )
    assert polished == _FLOOR_CASE_PLACED


def test_polish_floor_control_moves_without_the_dependency() -> None:
    inp = _floor_case_input(with_dependency=False)
    polished = polish_placements(
        list(_FLOOR_CASE_PLACED), inp, DEFAULT_PLACEMENT_SCORING_CONFIG
    )
    assert polished == [
        _placed("p_parent", _dt(1, 18), _dt(1, 19)),
        _placed("c_child", _dt(0, 9), _dt(0, 10)),
    ]


def _ceiling_case_input(*, with_dependency: bool) -> object:
    """Non-deep parent Mon 09:00 (stranding a sliver); deep child Tue 18:00.

    Moving the parent to Wed 09:00 heals the Mon fragmentation and strictly
    improves the total — but it would end after the dependent child starts,
    so the dependency ceiling must forbid it.
    """
    plan = make_plan(
        make_task(task_id="p_parent", estimated_duration_min=60),
        make_task(
            task_id="c_child",
            estimated_duration_min=60,
            required_focus_level="deep",
            dependencies=["p_parent"] if with_dependency else [],
        ),
    )
    return make_input(
        plan,
        policy=_TUE_ONLY_DEEP,
        free_busy=[
            busy(_dt(0, 8), minutes=60),  # Mon 08:00-09:00
            busy(_dt(0, 10, 15), minutes=735),  # Mon 10:15-22:30 (75-min window)
            busy(_dt(1, 8), minutes=600),  # Tue 08:00-18:00
            busy(_dt(1, 19), minutes=210),  # Tue 19:00-22:30
            busy(_dt(2, 8), minutes=60),  # Wed 08:00-09:00
            busy(_dt(2, 10), minutes=750),  # Wed 10:00-22:30
        ],
        horizon_days=3,
    )


_CEILING_CASE_PLACED = [
    _placed("p_parent", _dt(0, 9), _dt(0, 10)),
    _placed("c_child", _dt(1, 18), _dt(1, 19)),
]


def test_polish_respects_the_dependent_ceiling() -> None:
    inp = _ceiling_case_input(with_dependency=True)
    polished = polish_placements(
        list(_CEILING_CASE_PLACED), inp, DEFAULT_PLACEMENT_SCORING_CONFIG
    )
    assert polished == _CEILING_CASE_PLACED


def test_polish_ceiling_control_moves_without_the_dependency() -> None:
    inp = _ceiling_case_input(with_dependency=False)
    polished = polish_placements(
        list(_CEILING_CASE_PLACED), inp, DEFAULT_PLACEMENT_SCORING_CONFIG
    )
    assert polished == [
        _placed("p_parent", _dt(2, 9), _dt(2, 10)),
        _placed("c_child", _dt(1, 18), _dt(1, 19)),
    ]


# --------------------------------------------------------------------------- #
# Pairwise deep-gap check — both neighbors, not just the previous block
# --------------------------------------------------------------------------- #


def _deep_gap_input(*, evening_end: str) -> object:
    """Two deep tasks; deep windows Mon morning 09:00-10:00 + evening 18:00-…

    ``prefer_evening_sessions`` makes an evening slot strictly improving
    for the morning block; whether a gap-respecting evening candidate
    exists depends on ``evening_end``.
    """
    policy = DEEP_WORK_POLICY.model_copy(
        update={
            "prefer_evening_sessions": True,
            "deep_work_windows": [
                DeepWorkWindowPolicy(day="Mon", start="09:00", end="10:00"),
                DeepWorkWindowPolicy(day="Mon", start="18:00", end=evening_end),
            ],
        }
    )
    evening_end_h, evening_end_m = (int(p) for p in evening_end.split(":"))
    evening_busy_min = (22 * 60 + 30) - (evening_end_h * 60 + evening_end_m)
    plan = make_plan(
        make_task(
            task_id="d_one", estimated_duration_min=60, required_focus_level="deep"
        ),
        make_task(
            task_id="d_two", estimated_duration_min=60, required_focus_level="deep"
        ),
    )
    return make_input(
        plan,
        policy=policy,
        free_busy=[
            busy(_dt(0, 8), minutes=60),  # 08:00-09:00
            busy(_dt(0, 10), minutes=480),  # 10:00-18:00
            busy(
                _dt(0, evening_end_h, evening_end_m), minutes=evening_busy_min
            ),  # evening_end-22:30
        ],
        horizon_days=1,
    )


def test_polish_deep_gap_blocks_the_after_neighbor_violation() -> None:
    """The only improving candidate sits right before an existing deep block.

    The greedy loop's append-only bookkeeping only ever checked the
    *previous* deep block; the polish pairwise check must also catch a
    too-small gap to the *next* one (axiom 05) and make no move.
    """
    inp = _deep_gap_input(evening_end="20:00")
    placed = [
        _placed("d_one", _dt(0, 19), _dt(0, 20)),
        _placed("d_two", _dt(0, 9), _dt(0, 10)),
    ]
    polished = polish_placements(
        list(placed), inp, DEFAULT_PLACEMENT_SCORING_CONFIG
    )
    assert polished == placed  # 18:00-19:00 improves but gap to d_one is 0


def test_polish_deep_gap_allows_the_gap_respecting_move() -> None:
    """Twin scenario: a wider evening window offers a legal 20:00 start."""
    inp = _deep_gap_input(evening_end="21:00")
    placed = [
        _placed("d_one", _dt(0, 18), _dt(0, 19)),
        _placed("d_two", _dt(0, 9), _dt(0, 10)),
    ]
    polished = polish_placements(
        list(placed), inp, DEFAULT_PLACEMENT_SCORING_CONFIG
    )
    assert polished == [
        _placed("d_one", _dt(0, 18), _dt(0, 19)),
        _placed("d_two", _dt(0, 20), _dt(0, 21)),
    ]
