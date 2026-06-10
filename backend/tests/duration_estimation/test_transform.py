"""Direct tests for ``duration_estimation.transform.apply_duration_calibration``.

The transform previously had only indirect coverage via ``planning.replan``;
these tests pin the documented determinism guarantees — round-half-up,
floor-at-1, no-op cases, ordering, and the diff building blocks.
"""

from __future__ import annotations

from datetime import UTC, datetime

from agentic_calendar.contracts.common_types import TaskCategory
from agentic_calendar.contracts.plan_diff import DiffChangeType
from agentic_calendar.contracts.reason_codes import ReasonCode
from agentic_calendar.contracts.task_plan import TaskPlan
from agentic_calendar.contracts.user_duration_multipliers import (
    CategoryMultiplier,
    UserDurationMultipliers,
)
from agentic_calendar.duration_estimation import apply_duration_calibration
from agentic_calendar.duration_estimation.transform import _round_half_up

_TS = datetime(2026, 5, 4, 12, 0, tzinfo=UTC)


def _plan(*tasks: dict[str, object], plan_version: str = "plan_v1") -> TaskPlan:
    return TaskPlan.model_validate(
        {"plan_version": plan_version, "tasks": list(tasks)}
    )


def _task(
    task_id: str,
    *,
    duration: int = 60,
    category: str = "practice",
) -> dict[str, object]:
    return {
        "task_id": task_id,
        "module_id": "dp",
        "title": "t",
        "dependencies": [],
        "estimated_duration_min": duration,
        "cognitive_load": 3,
        "category": category,
        "required_focus_level": "medium",
        "splittable": False,
    }


def _multipliers(
    factor: float, category: TaskCategory = TaskCategory.PRACTICE
) -> UserDurationMultipliers:
    return UserDurationMultipliers(
        user_id="u1",
        computed_at=_TS,
        multipliers=[
            CategoryMultiplier(
                category=category,
                multiplier=factor,
                sample_size=6,
                observed_ratio=factor,
            )
        ],
    )


def test_round_half_up_halves_go_up() -> None:
    assert _round_half_up(2.5) == 3
    assert _round_half_up(3.5) == 4
    assert _round_half_up(2.4) == 2
    assert _round_half_up(2.6) == 3
    assert _round_half_up(0.0) == 0


def test_scaling_rounds_half_up_to_whole_minute() -> None:
    # 45 * 1.5 = 67.5 -> rounds UP to 68 (not banker's 67).
    result = apply_duration_calibration(
        _plan(_task("a", duration=45)), _multipliers(1.5), to_plan_version="plan_v2"
    )
    assert result.plan.tasks[0].estimated_duration_min == 68
    assert result.field_changes[0].old_value == 45
    assert result.field_changes[0].new_value == 68
    assert result.field_changes[0].delta_minutes == 23


def test_scaled_duration_floors_at_one_minute() -> None:
    # 1 * 0.1 = 0.1 -> rounds to 0 -> floored to the contract minimum of 1...
    # which equals the original, so the task is carried through unchanged.
    result = apply_duration_calibration(
        _plan(_task("a", duration=1)), _multipliers(0.1), to_plan_version="plan_v2"
    )
    assert result.plan.tasks[0].estimated_duration_min == 1
    assert result.changed is False

    # 3 * 0.1 = 0.3 -> rounds to 0 -> floored to 1 (a real change).
    result = apply_duration_calibration(
        _plan(_task("a", duration=3)), _multipliers(0.1), to_plan_version="plan_v2"
    )
    assert result.plan.tasks[0].estimated_duration_min == 1
    assert result.changed is True


def test_rounding_noop_produces_no_field_change() -> None:
    # 60 * 1.004 = 60.24 -> rounds back to 60: no change recorded.
    result = apply_duration_calibration(
        _plan(_task("a", duration=60)), _multipliers(1.004), to_plan_version="plan_v2"
    )
    assert result.changed is False
    assert result.field_changes == ()
    assert result.task_changes == ()
    assert result.plan.tasks[0].estimated_duration_min == 60
    # The requested version is stamped even when nothing changed.
    assert result.plan.plan_version == "plan_v2"


def test_unmatched_category_and_unit_multiplier_are_noops() -> None:
    plan = _plan(_task("a", duration=60))
    for mult in (
        _multipliers(1.0),
        _multipliers(2.0, category=TaskCategory.REVIEW),
    ):
        result = apply_duration_calibration(plan, mult, to_plan_version="plan_v2")
        assert result.changed is False
        assert result.plan.tasks[0].estimated_duration_min == 60


def test_changes_carry_reason_code_and_preserve_task_order() -> None:
    result = apply_duration_calibration(
        _plan(
            _task("a", duration=60),
            _task("b", duration=30, category="review"),
            _task("c", duration=90),
        ),
        _multipliers(1.5),
        to_plan_version="plan_v2",
    )
    # Only practice tasks scale; output order follows input order.
    assert [t.task_id for t in result.plan.tasks] == ["a", "b", "c"]
    assert result.changed_task_ids == ("a", "c")
    for fc in result.field_changes:
        assert fc.reason_code is ReasonCode.USER_DURATION_CALIBRATION
    for tc in result.task_changes:
        assert tc.change_type is DiffChangeType.DURATION_CHANGED
    assert result.plan.tasks[1].estimated_duration_min == 30  # untouched


def test_input_plan_is_not_mutated() -> None:
    plan = _plan(_task("a", duration=60))
    apply_duration_calibration(plan, _multipliers(1.5), to_plan_version="plan_v2")
    assert plan.tasks[0].estimated_duration_min == 60
    assert plan.plan_version == "plan_v1"
