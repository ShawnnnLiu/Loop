"""Tests for ``validation.scheduling_preconditions``."""

from __future__ import annotations

from agentic_calendar.validation.scheduling_preconditions import (
    check_scheduling_preconditions,
)
from tests.validation._helpers import make_plan, make_task


def test_root_task_present_no_violations() -> None:
    plan = make_plan(
        make_task(task_id="a"),
        make_task(task_id="b", dependencies=["a"]),
    )
    assert check_scheduling_preconditions(plan) == []


def test_no_root_task_reports_violation() -> None:
    """Bypass model validation: every task depends on every other → no root.

    Use ``model_construct`` so the contract doesn't reject the structure
    before the precondition checker can fire.
    """
    from agentic_calendar.contracts.common_types import FocusLevel, TaskCategory
    from agentic_calendar.contracts.task_plan import Task, TaskPlan

    def t(task_id: str, deps: list[str]) -> Task:
        return Task.model_construct(
            task_id=task_id,
            module_id="dp",
            title=task_id,
            description="",
            dependencies=deps,
            estimated_duration_min=60,
            cognitive_load=3,
            category=TaskCategory.PRACTICE,
            required_focus_level=FocusLevel.MEDIUM,
            splittable=False,
        )

    plan = TaskPlan.model_construct(
        plan_version="p", tasks=[t("a", ["b"]), t("b", ["a"])]
    )
    violations = check_scheduling_preconditions(plan)
    assert len(violations) == 1
    assert violations[0].details["details_summary"] == "no_root_task"
