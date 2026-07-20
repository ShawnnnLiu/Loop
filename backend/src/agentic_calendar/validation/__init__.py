"""Five-category validation layer (``docs/axioms/04-validation-layer.md``).

Each checker module is independent: schema, graph, coverage, user_fit, and
scheduling_preconditions. The orchestrator composes them and returns a
``ValidationResult``. Validation must never mutate the artifact under test.

Phase 5 wires ``validate_syllabus_units`` (axiom 08): once source claims carry
deterministic confidence and expiry, a syllabus that references missing or
expired claims must be caught and routed to a Strategist repair before the
Planner consumes it. ``validate_user_profile`` / ``validate_motivation_profile``
remain deferred (their Pydantic contracts reject malformed artifacts at parse
time and there is no LLM producer for them yet); the ``ArtifactType`` enum
reserves the slots so adding them stays purely additive.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from agentic_calendar.contracts.pathway_template import PathwayTemplate
from agentic_calendar.contracts.reason_codes import ReasonCode
from agentic_calendar.contracts.source_claim import SourceClaim
from agentic_calendar.contracts.syllabus_units import SyllabusUnits
from agentic_calendar.contracts.task_plan import TaskPlan
from agentic_calendar.contracts.translations import user_facing
from agentic_calendar.contracts.user_profile import UserProfile
from agentic_calendar.contracts.validation_result import (
    MAX_REPAIR_ATTEMPTS_LLM,
    ArtifactType,
    NextAction,
    ValidationResult,
    Violation,
)
from agentic_calendar.contracts.violation_types import ViolationType

from .coverage import check_coverage
from .graph import check_task_graph
from .pathway import check_pathway_slots
from .repair import RepairPayload, next_action_for
from .scheduling_preconditions import check_scheduling_preconditions
from .schema import check_syllabus_units_shape, check_task_plan_shape
from .source_claims import check_source_claims
from .user_fit import check_user_fit

__all__ = [
    "RepairPayload",
    "ValidationResult",
    "Violation",
    "next_action_for",
    "user_facing",
    "validate_syllabus_units",
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


def validate_syllabus_units(
    syllabus: SyllabusUnits | dict[str, Any],
    *,
    claim_registry: Mapping[str, SourceClaim],
    now: datetime,
    run_id: str,
    must_reference_claims_for_company_specific_modules: bool = True,
    selected_pathway: PathwayTemplate | None = None,
    max_slot_modules: int = 3,
    repair_attempt: int = 0,
) -> ValidationResult:
    """Validate a ``SyllabusUnits`` proposal's source-claim + slot integrity.

    Checks that every referenced ``source_claim_id`` resolves to a known,
    non-expired claim (axiom 08), that company-specific modules cite evidence
    when required, and that any ``evidence_slot_id`` links resolve to slots of
    the selected pathway within the ``max_slot_modules`` bound (narrative
    pathways, NP-D). A failure routes to a Strategist repair (the Strategist is
    the artifact's producer); success is a benign ``NOOP`` — the orchestrator
    then proceeds to the Planner outside this result.

    ``selected_pathway`` / ``max_slot_modules`` come from the composition root:
    the same ``StrategyConstraints`` the Strategist was handed, so the gate
    disposes exactly what the prompt was told to respect. With no pathway
    selected, ``selected_pathway`` is ``None`` and any slot link is rejected as
    ``PATHWAY_NOT_SELECTED``.
    """
    # Shape first: a malformed raw dict becomes typed violations, never a raw
    # ValidationError (axiom 04 / 16), mirroring ``validate_task_plan``.
    shape_violations = check_syllabus_units_shape(syllabus)
    if shape_violations:
        violations = shape_violations
    else:
        parsed = (
            syllabus
            if isinstance(syllabus, SyllabusUnits)
            else SyllabusUnits.model_validate(syllabus)
        )
        violations = check_source_claims(
            parsed,
            claim_registry=claim_registry,
            now=now,
            must_reference_claims_for_company_specific_modules=(
                must_reference_claims_for_company_specific_modules
            ),
        )
        violations.extend(
            check_pathway_slots(
                parsed,
                selected_pathway=selected_pathway,
                max_slot_modules=max_slot_modules,
            )
        )

    valid = not violations
    reason_code: ReasonCode | None = None if valid else _summarize_reason(violations)
    repairable = not valid
    next_action = _syllabus_next_action(valid=valid, repair_attempt=repair_attempt)

    return ValidationResult(
        run_id=run_id,
        artifact_type=ArtifactType.SYLLABUS_UNITS,
        valid=valid,
        repairable=repairable if not valid else False,
        reason_code=reason_code,
        violations=violations,
        repair_attempt=repair_attempt,
        next_action=next_action,
    )


def _syllabus_next_action(*, valid: bool, repair_attempt: int) -> NextAction:
    """Next step for a syllabus result: repair via the Strategist, or proceed.

    Unlike a validated ``task_plan`` (which advances to the Scheduler), a valid
    syllabus has no in-band next action here — the orchestrator advances it to
    the Planner — so success is ``NOOP``. Failure routes to a bounded Strategist
    repair, then to the user once the cap is hit (axiom 04).
    """
    if valid:
        return NextAction.NOOP
    if repair_attempt < MAX_REPAIR_ATTEMPTS_LLM:
        return NextAction.STRATEGIST_REPAIR_RETRY
    return NextAction.ERROR_REQUIRES_USER


def _summarize_reason(violations: list[Violation]) -> ReasonCode:
    """Pick a single ``ReasonCode`` that summarises a non-empty violation list.

    Order of precedence (most actionable first):

    1. forbidden field present (axiom 11)
    2. graph integrity
    3. scheduling preconditions (structural — must come before coverage so a
       deadlocked plan reports the right reason)
    4. coverage
    5. source claims (axiom 08 — missing/expired evidence; syllabus stage)
    6. narrative-pathway slot linkage (NP-D — each type its own reason code)
    7. user fit
    8. generic schema invalid (fallback)
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

    scheduling_precondition_types = {
        ViolationType.NO_ROOT_TASK,
    }
    if types & scheduling_precondition_types:
        return ReasonCode.SCHEDULING_PRECONDITION_FAILED

    coverage_types = {
        ViolationType.MODULE_COVERAGE_MISSING,
        ViolationType.MISSING_MODULE_ID,
        ViolationType.LOW_PRIORITY_MODULE_OVERWEIGHTED,
    }
    if types & coverage_types:
        return ReasonCode.MODULE_COVERAGE_INSUFFICIENT

    source_claim_types = {
        ViolationType.ORPHAN_SOURCE_CLAIM,
        ViolationType.EXPIRED_SOURCE_CLAIM,
        ViolationType.COMPANY_MODULE_MISSING_CLAIM,
    }
    if types & source_claim_types:
        return ReasonCode.SOURCE_CLAIM_VALIDATION_FAILED

    # Narrative-pathway slot linkage (NP-D). Each violation type maps to its own
    # reason code (unlike the categories above, which collapse to one), so a
    # single-issue syllabus surfaces the actionable code; ties break in the
    # order below (selection missing is the most fundamental).
    if ViolationType.PATHWAY_NOT_SELECTED in types:
        return ReasonCode.PATHWAY_NOT_SELECTED
    if ViolationType.UNKNOWN_EVIDENCE_SLOT in types:
        return ReasonCode.UNKNOWN_EVIDENCE_SLOT
    if ViolationType.SLOT_MODULE_LIMIT_EXCEEDED in types:
        return ReasonCode.SLOT_MODULE_LIMIT_EXCEEDED

    user_fit_types = {
        ViolationType.DURATION_EXCEEDS_USER_MAX_SESSION,
        ViolationType.DURATION_FAR_FROM_PREFERRED,
        ViolationType.WEEKLY_LOAD_EXCEEDS_CAPACITY,
        ViolationType.COGNITIVE_LOAD_OUT_OF_RANGE,
        ViolationType.HIGH_LOAD_TASKS_NOT_DISTRIBUTED,
        ViolationType.CATEGORY_INVALID,
        ViolationType.FOCUS_LEVEL_INVALID,
    }
    if types & user_fit_types:
        return ReasonCode.USER_FIT_VIOLATED

    return ReasonCode.SCHEMA_INVALID
