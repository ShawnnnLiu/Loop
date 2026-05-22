"""Tests for ``compute_runtime_view`` against a real ``TaskPlan``."""

from __future__ import annotations

from agentic_calendar.contracts.task_plan import TaskPlan
from agentic_calendar.prerequisites.compute import (
    compute_runtime_view,
    eligible_task_ids,
)
from tests._fixture_loader import iter_valid

VALID_PLAN_PAYLOAD = next(iter_valid("task_plan")).payload


def _plan() -> TaskPlan:
    return TaskPlan.model_validate(VALID_PLAN_PAYLOAD)


def test_no_completions_root_tasks_eligible() -> None:
    plan = _plan()
    runtime = compute_runtime_view(plan)
    by_id = {rt.task_id: rt for rt in runtime}
    assert by_id["dp_001"].prerequisites_met is True
    assert by_id["dp_001"].blocked_by == []
    assert by_id["dp_001"].eligible_for_scheduling is True
    assert by_id["dp_002"].prerequisites_met is False
    assert by_id["dp_002"].blocked_by == ["dp_001"]
    assert by_id["dp_002"].eligible_for_scheduling is False


def test_completion_unlocks_dependent() -> None:
    plan = _plan()
    runtime = compute_runtime_view(plan, completed_task_ids={"dp_001"})
    by_id = {rt.task_id: rt for rt in runtime}
    assert by_id["dp_002"].prerequisites_met is True
    assert by_id["dp_002"].blocked_by == []


def test_eligible_task_ids_helper() -> None:
    plan = _plan()
    assert eligible_task_ids(plan) == ["dp_001"]
    assert eligible_task_ids(plan, completed_task_ids={"dp_001"}) == [
        "dp_001",
        "dp_002",
    ]


def test_compute_does_not_mutate_input() -> None:
    plan = _plan()
    snapshot = plan.model_dump()
    compute_runtime_view(plan, completed_task_ids={"dp_001"})
    assert plan.model_dump() == snapshot


def test_runtime_view_preserves_input_order() -> None:
    plan = _plan()
    runtime = compute_runtime_view(plan)
    assert [rt.task_id for rt in runtime] == [t.task_id for t in plan.tasks]
