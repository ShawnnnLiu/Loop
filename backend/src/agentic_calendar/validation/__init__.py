"""Five-category validation layer (``docs/axioms/04-validation-layer.md``).

Each checker module is independent: schema, graph, coverage, user_fit, and
scheduling_preconditions. The orchestrator composes them and returns a
``ValidationResult``. Validation must never mutate the artifact under test.
"""

from __future__ import annotations

from typing import Any

from agentic_calendar.contracts.reason_codes import ReasonCode
from agentic_calendar.contracts.syllabus_units import SyllabusUnits
from agentic_calendar.contracts.task_plan import TaskPlan
from agentic_calendar.contracts.translations import user_facing
from agentic_calendar.contracts.user_profile import UserProfile
from agentic_calendar.contracts.validation_result import (
    ArtifactType,
    ValidationResult,
    Violation,
)
from agentic_calendar.contracts.violation_types import ViolationType

from .coverage import check_coverage
from .graph import check_task_graph
from .repair import RepairPayload, next_action_for
from .scheduling_preconditions import check_scheduling_preconditions
from .schema import check_task_plan_shape
from .user_fit import check_user_fit

__all__ = [
    "RepairPayload",
    "ValidationResult",
    "Violation",
    "next_action_for",
    "user_facing",
    "validate_task_plan",
]


def validate_task_plan(
    plan: TaskPlan | dict[str, Any],
    *,
    syllabus: SyllabusUnits,
    user_profile: UserProfile,
    run_id: str,
    repair_attempt: int = 0,
) -> ValidationResult:
    """Run all five checkers against ``plan`` and return a typed result.

    The plan may be a parsed ``TaskPlan`` or a raw dict. In the dict case,
    schema-shape failures are surfaced as ``Violation`` records (so callers
    never see a Pydantic ``ValidationError`` from this layer).
    """
    violations: list[Violation] = []

    shape_violations = check_task_plan_shape(plan)
    violations.extend(shape_violations)

    parsed: TaskPlan | None
    if isinstance(plan, TaskPlan):
        parsed = plan
    elif not shape_violations:
        parsed = TaskPlan.model_validate(plan)
    else:
        parsed = None

    if parsed is not None:
        violations.extend(check_task_graph(parsed))
        violations.extend(check_coverage(parsed, syllabus))
        violations.extend(check_user_fit(parsed, user_profile))
        violations.extend(check_scheduling_preconditions(parsed))

    valid = not violations
    reason_code: ReasonCode | None = None if valid else _summarize_reason(violations)
    repairable = not valid
    next_action = next_action_for(
        valid=valid, repair_attempt=repair_attempt, repairable=repairable
    )

    return ValidationResult(
        run_id=run_id,
        artifact_type=ArtifactType.TASK_PLAN,
        valid=valid,
        repairable=repairable if not valid else False,
        reason_code=reason_code,
        violations=violations,
        repair_attempt=repair_attempt,
        next_action=next_action,
    )


def _summarize_reason(violations: list[Violation]) -> ReasonCode:
    """Pick a single ``ReasonCode`` that summarises a non-empty violation list.

    Order of precedence (most actionable first):

    1. forbidden field present (axiom 11)
    2. graph integrity
    3. coverage
    4. user fit
    5. scheduling preconditions
    6. generic schema invalid
    """
    types = {v.type for v in violations}

    if ViolationType.FORBIDDEN_FIELD_PRESENT in types:
        return ReasonCode.FORBIDDEN_FIELD_PRESENT

    graph_types = {
        ViolationType.DUPLICATE_TASK_ID,
        ViolationType.ORPHAN_DEPENDENCY,
        ViolationType.SELF_DEPENDENCY,
        ViolationType.CYCLE_DETECTED,
    }
    if types & graph_types:
        return ReasonCode.TASK_GRAPH_INVALID

    coverage_types = {
        ViolationType.MODULE_COVERAGE_MISSING,
        ViolationType.MISSING_MODULE_ID,
        ViolationType.LOW_PRIORITY_MODULE_OVERWEIGHTED,
    }
    if types & coverage_types:
        return ReasonCode.MODULE_COVERAGE_INSUFFICIENT

    user_fit_types = {
        ViolationType.DURATION_EXCEEDS_USER_MAX_SESSION,
        ViolationType.WEEKLY_LOAD_EXCEEDS_CAPACITY,
        ViolationType.COGNITIVE_LOAD_OUT_OF_RANGE,
        ViolationType.HIGH_LOAD_TASKS_NOT_DISTRIBUTED,
        ViolationType.CATEGORY_INVALID,
        ViolationType.FOCUS_LEVEL_INVALID,
    }
    if types & user_fit_types:
        return ReasonCode.USER_FIT_VIOLATED

    return ReasonCode.SCHEMA_INVALID
