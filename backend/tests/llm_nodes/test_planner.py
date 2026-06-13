"""Tests for ``llm_nodes.planner.FixturePlanner``."""

from __future__ import annotations

import pytest

from agentic_calendar.contracts.reason_codes import ReasonCode
from agentic_calendar.contracts.syllabus_units import SyllabusUnits
from agentic_calendar.contracts.task_plan import TaskPlan
from agentic_calendar.contracts.user_profile import UserProfile
from agentic_calendar.contracts.validation_result import (
    ArtifactType,
    NextAction,
    ValidationResult,
    Violation,
)
from agentic_calendar.contracts.violation_types import ViolationType
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


def test_protocol_parity_kwargs_are_accepted_and_ignored() -> None:
    """``user_profile`` and ``repair`` (PlannerNode surface) leave the canned
    output byte-identical — the fixture cannot honor them."""
    syl = _syllabus()
    plan = _task_plan()
    node = FixturePlanner({syl.syllabus_version: plan})
    profile = UserProfile.model_validate(next(iter_valid("user_profile")).payload)
    repair = ValidationResult(
        run_id="r",
        artifact_type=ArtifactType.TASK_PLAN,
        valid=False,
        repairable=True,
        reason_code=ReasonCode.USER_FIT_VIOLATED,
        violations=[
            Violation(
                type=ViolationType.DURATION_EXCEEDS_USER_MAX_SESSION,
                task_id="dp_001",
            )
        ],
        repair_attempt=1,
        next_action=NextAction.PLANNER_REPAIR_RETRY,
    )

    out = node.run(run_id="r", syllabus=syl, user_profile=profile, repair=repair)

    assert out.model_dump(mode="json") == node.run(
        run_id="r", syllabus=syl
    ).model_dump(mode="json")
