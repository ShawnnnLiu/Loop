"""Tests for ``llm_nodes.planner.FixturePlanner``."""

from __future__ import annotations

import pytest

from agentic_calendar.contracts.syllabus_units import SyllabusUnits
from agentic_calendar.contracts.task_plan import TaskPlan
from agentic_calendar.llm_nodes import FixturePlanner
from agentic_calendar.llm_nodes.base import LLMNodeError
from tests._fixture_loader import iter_valid


def _syllabus() -> SyllabusUnits:
    return SyllabusUnits.model_validate(next(iter_valid("syllabus_units")).payload)


def _task_plan() -> TaskPlan:
    return TaskPlan.model_validate(next(iter_valid("task_plan")).payload)


def test_returns_fixture_keyed_by_syllabus_version() -> None:
    syl = _syllabus()
    plan = _task_plan()
    node = FixturePlanner({syl.syllabus_version: plan})
    out = node.run(run_id="r", syllabus=syl)
    assert isinstance(out, TaskPlan)
    assert out.plan_version == plan.plan_version


def test_unknown_syllabus_version_raises() -> None:
    syl = _syllabus()
    plan = _task_plan()
    node = FixturePlanner({"different_syllabus": plan})
    with pytest.raises(LLMNodeError):
        node.run(run_id="r", syllabus=syl)


def test_empty_fixtures_rejected() -> None:
    with pytest.raises(ValueError):
        FixturePlanner({})
