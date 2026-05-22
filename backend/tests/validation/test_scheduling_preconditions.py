"""Tests for ``validation.scheduling_preconditions``."""

from __future__ import annotations

from agentic_calendar.contracts.violation_types import ViolationType
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


def test_no_root_task_reports_typed_violation() -> None:
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
    assert violations[0].type is ViolationType.NO_ROOT_TASK


def test_no_root_task_summarises_through_orchestrator() -> None:
    """End-to-end through the orchestrator: NO_ROOT_TASK lands in violations.

    The summary code in this artificial scenario is ``TASK_GRAPH_INVALID``
    because the same input also produces a cycle (every task depending on
    another implies one). The point of this test is to confirm the
    precondition layer's typed violation is not silently swallowed.
    """
    from agentic_calendar.contracts.common_types import FocusLevel, TaskCategory
    from agentic_calendar.contracts.reason_codes import ReasonCode
    from agentic_calendar.contracts.task_plan import Task, TaskPlan
    from agentic_calendar.validation import validate_task_plan
    from tests.validation._helpers import load_syllabus, load_user_profile

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
    result = validate_task_plan(
        plan,
        syllabus=load_syllabus(),
        user_profile=load_user_profile(),
        run_id="r_precond",
    )
    types = {v.type for v in result.violations}
    assert ViolationType.NO_ROOT_TASK in types
    assert result.reason_code is ReasonCode.TASK_GRAPH_INVALID
