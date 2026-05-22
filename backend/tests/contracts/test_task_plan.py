"""Tests for ``TaskPlan`` and ``Task``.

Includes the explicit "prerequisites_met is forbidden" rule (axiom 11).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from agentic_calendar.contracts.task_plan import TaskPlan
from tests._fixture_loader import iter_invalid, iter_valid

CONTRACT = "task_plan"


@pytest.mark.parametrize(
    "fixture",
    list(iter_valid(CONTRACT)),
    ids=lambda f: f.name,
)
def test_valid_fixture_parses(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    plan = TaskPlan.model_validate(payload)
    assert plan.plan_version == payload["plan_version"]
    assert len(plan.tasks) == len(payload["tasks"])


@pytest.mark.parametrize(
    "fixture",
    list(iter_invalid(CONTRACT)),
    ids=lambda f: f.name,
)
def test_invalid_fixture_rejected(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    expected = fixture.expected  # type: ignore[attr-defined]
    with pytest.raises(ValidationError) as exc_info:
        TaskPlan.model_validate(payload)
    msg = str(exc_info.value)
    for substr in expected["error_substrings"]:
        assert substr in msg, (
            f"expected substring {substr!r} not in error message:\n{msg}"
        )


def test_prerequisites_met_is_forbidden_message_mentions_axiom() -> None:
    """Spec-defining test: ``prerequisites_met`` must produce an axiom-aware error."""
    payload = {
        "plan_version": "p_x",
        "tasks": [
            {
                "task_id": "t1",
                "module_id": "m1",
                "title": "t",
                "dependencies": [],
                "estimated_duration_min": 30,
                "cognitive_load": 2,
                "category": "practice",
                "required_focus_level": "medium",
                "splittable": False,
                "prerequisites_met": False,
            }
        ],
    }
    with pytest.raises(ValidationError) as exc_info:
        TaskPlan.model_validate(payload)
    msg = str(exc_info.value)
    assert "prerequisites_met" in msg
    assert "forbidden" in msg
    assert "axiom 11" in msg


def test_no_tasks_rejected() -> None:
    with pytest.raises(ValidationError):
        TaskPlan.model_validate({"plan_version": "p", "tasks": []})


def test_task_plan_does_not_define_prerequisites_met_attribute() -> None:
    """The model should not even expose ``prerequisites_met`` as an attribute."""
    from agentic_calendar.contracts.task_plan import Task

    assert "prerequisites_met" not in Task.model_fields
