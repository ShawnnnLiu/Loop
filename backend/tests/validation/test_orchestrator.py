"""End-to-end tests for ``validation.validate_task_plan``.

These exercise the full orchestrator: shape check → graph → coverage →
user-fit → scheduling preconditions → ``ValidationResult``.
"""

from __future__ import annotations

from agentic_calendar.contracts.reason_codes import ReasonCode
from agentic_calendar.contracts.validation_result import (
    ArtifactType,
    NextAction,
    ValidationResult,
)
from agentic_calendar.validation import validate_task_plan
from tests.validation._helpers import (
    load_syllabus,
    load_user_profile,
    make_plan,
    make_task,
)


def test_valid_plan_routes_to_scheduler() -> None:
    syllabus = load_syllabus()
    user = load_user_profile()
    plan = make_plan(
        make_task(task_id="dp_001", module_id="dp"),
        make_task(task_id="api_001", module_id="api_design"),
    )
    result = validate_task_plan(
        plan, syllabus=syllabus, user_profile=user, run_id="run_001"
    )
    assert isinstance(result, ValidationResult)
    assert result.valid is True
    assert result.violations == []
    assert result.reason_code is None
    assert result.next_action is NextAction.SCHEDULER
    assert result.artifact_type is ArtifactType.TASK_PLAN


def test_invalid_plan_with_orphan_dep_summarised_as_graph_invalid() -> None:
    syllabus = load_syllabus()
    user = load_user_profile()
    plan = make_plan(
        make_task(task_id="dp_001", module_id="dp"),
        make_task(task_id="api_001", module_id="api_design", dependencies=["ghost"]),
    )
    result = validate_task_plan(
        plan, syllabus=syllabus, user_profile=user, run_id="run_002"
    )
    assert result.valid is False
    assert result.reason_code is ReasonCode.TASK_GRAPH_INVALID
    assert result.next_action is NextAction.PLANNER_REPAIR_RETRY


def test_repair_attempt_at_cap_routes_to_error_requires_user() -> None:
    syllabus = load_syllabus()
    user = load_user_profile()
    plan = make_plan(
        make_task(task_id="api_001", module_id="api_design"),  # missing dp coverage
    )
    result = validate_task_plan(
        plan,
        syllabus=syllabus,
        user_profile=user,
        run_id="run_003",
        repair_attempt=2,
    )
    assert result.valid is False
    assert result.next_action is NextAction.ERROR_REQUIRES_USER


def test_dict_input_with_forbidden_field_returns_typed_violation() -> None:
    syllabus = load_syllabus()
    user = load_user_profile()
    payload = {
        "plan_version": "p",
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
    result = validate_task_plan(
        payload, syllabus=syllabus, user_profile=user, run_id="run_004"
    )
    assert result.valid is False
    assert result.reason_code is ReasonCode.FORBIDDEN_FIELD_PRESENT


def test_validation_does_not_mutate_artifact() -> None:
    syllabus = load_syllabus()
    user = load_user_profile()
    plan = make_plan(
        make_task(task_id="dp_001", module_id="dp"),
        make_task(task_id="api_001", module_id="api_design"),
    )
    snapshot = plan.model_dump()
    validate_task_plan(
        plan, syllabus=syllabus, user_profile=user, run_id="run_005"
    )
    assert plan.model_dump() == snapshot


def test_unknown_module_summarised_as_coverage_insufficient() -> None:
    """MISSING_MODULE_ID must route through ``_summarize_reason`` to the
    ``MODULE_COVERAGE_INSUFFICIENT`` reason code end-to-end."""
    syllabus = load_syllabus()
    user = load_user_profile()
    plan = make_plan(
        make_task(task_id="dp_001", module_id="dp"),
        make_task(task_id="ghost", module_id="not_in_syllabus"),
    )
    result = validate_task_plan(
        plan, syllabus=syllabus, user_profile=user, run_id="run_cov"
    )
    assert result.valid is False
    assert result.reason_code is ReasonCode.MODULE_COVERAGE_INSUFFICIENT
    assert result.next_action is NextAction.PLANNER_REPAIR_RETRY


def test_capacity_overflow_summarised_as_user_fit() -> None:
    syllabus = load_syllabus()
    user = load_user_profile()
    huge_count = int(user.weekly_hours * 60 * user.timeline_weeks * 1.2 / 60) + 10
    plan = make_plan(
        *[
            make_task(task_id=f"dp_{i:03d}", module_id="dp", estimated_duration_min=60)
            for i in range(huge_count)
        ],
        make_task(task_id="api_001", module_id="api_design"),
    )
    result = validate_task_plan(
        plan, syllabus=syllabus, user_profile=user, run_id="run_006"
    )
    assert result.valid is False
    assert result.reason_code is ReasonCode.USER_FIT_VIOLATED
