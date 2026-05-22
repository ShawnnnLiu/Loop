"""Shared helpers for validation tests."""

from __future__ import annotations

from typing import Any

from agentic_calendar.contracts.syllabus_units import SyllabusUnits
from agentic_calendar.contracts.task_plan import TaskPlan
from agentic_calendar.contracts.user_profile import UserProfile
from tests._fixture_loader import iter_valid


def load_user_profile() -> UserProfile:
    return UserProfile.model_validate(next(iter_valid("user_profile")).payload)


def load_syllabus() -> SyllabusUnits:
    return SyllabusUnits.model_validate(next(iter_valid("syllabus_units")).payload)


def make_task(
    *,
    task_id: str = "t1",
    module_id: str = "dp",
    title: str = "Test task",
    dependencies: list[str] | None = None,
    estimated_duration_min: int = 60,
    cognitive_load: int = 3,
    category: str = "practice",
    required_focus_level: str = "medium",
    splittable: bool = False,
) -> dict[str, Any]:
    return {
        "task_id": task_id,
        "module_id": module_id,
        "title": title,
        "dependencies": list(dependencies or []),
        "estimated_duration_min": estimated_duration_min,
        "cognitive_load": cognitive_load,
        "category": category,
        "required_focus_level": required_focus_level,
        "splittable": splittable,
    }


def make_plan(*tasks: dict[str, Any], plan_version: str = "plan_test") -> TaskPlan:
    return TaskPlan.model_validate({"plan_version": plan_version, "tasks": list(tasks)})
