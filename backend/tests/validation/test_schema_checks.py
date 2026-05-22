"""Tests for ``validation.schema.check_task_plan_shape``."""

from __future__ import annotations

from agentic_calendar.contracts.task_plan import TaskPlan
from agentic_calendar.contracts.violation_types import ViolationType
from agentic_calendar.validation.schema import check_task_plan_shape
from tests._fixture_loader import iter_valid


def test_parsed_plan_returns_no_violations() -> None:
    plan = TaskPlan.model_validate(next(iter_valid("task_plan")).payload)
    assert check_task_plan_shape(plan) == []


def test_dict_plan_returns_no_violations_when_valid() -> None:
    payload = next(iter_valid("task_plan")).payload
    assert check_task_plan_shape(payload) == []


def test_missing_required_field_translated() -> None:
    payload = {
        "plan_version": "p1",
        "tasks": [
            {
                "task_id": "t1",
                "module_id": "dp",
                "dependencies": [],
                "estimated_duration_min": 60,
                "cognitive_load": 3,
                "category": "practice",
                "required_focus_level": "medium",
                "splittable": False,
            }
        ],
    }
    violations = check_task_plan_shape(payload)
    assert any(
        v.type is ViolationType.REQUIRED_FIELD_MISSING for v in violations
    )


def test_forbidden_field_translated_with_axiom_aware_violation() -> None:
    payload = {
        "plan_version": "p1",
        "tasks": [
            {
                "task_id": "t1",
                "module_id": "dp",
                "title": "x",
                "dependencies": [],
                "estimated_duration_min": 60,
                "cognitive_load": 3,
                "category": "practice",
                "required_focus_level": "medium",
                "splittable": False,
                "prerequisites_met": True,
            }
        ],
    }
    violations = check_task_plan_shape(payload)
    matching = [
        v for v in violations if v.type is ViolationType.FORBIDDEN_FIELD_PRESENT
    ]
    assert len(matching) == 1
    v = matching[0]
    assert v.task_id == "t1"
    assert v.details.get("field") == "prerequisites_met"


def test_invalid_enum_translated() -> None:
    payload = {
        "plan_version": "p1",
        "tasks": [
            {
                "task_id": "t1",
                "module_id": "dp",
                "title": "x",
                "dependencies": [],
                "estimated_duration_min": 60,
                "cognitive_load": 3,
                "category": "yoga",
                "required_focus_level": "medium",
                "splittable": False,
            }
        ],
    }
    violations = check_task_plan_shape(payload)
    assert any(v.type is ViolationType.ENUM_VALUE_INVALID for v in violations)
