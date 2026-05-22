"""Tests for ``llm_nodes.user_facing_explanation``."""

from __future__ import annotations

from agentic_calendar.contracts.reason_codes import ReasonCode
from agentic_calendar.contracts.validation_result import (
    ArtifactType,
    NextAction,
    ValidationResult,
    Violation,
)
from agentic_calendar.contracts.violation_types import ViolationType
from agentic_calendar.llm_nodes import (
    DeterministicUserFacingExplanation,
    UserExplanation,
)


def _success() -> ValidationResult:
    return ValidationResult(
        run_id="r",
        artifact_type=ArtifactType.TASK_PLAN,
        valid=True,
        repairable=False,
        repair_attempt=0,
        next_action=NextAction.SCHEDULER,
    )


def _failure(*types: ViolationType) -> ValidationResult:
    return ValidationResult(
        run_id="r",
        artifact_type=ArtifactType.TASK_PLAN,
        valid=False,
        repairable=True,
        reason_code=ReasonCode.TASK_GRAPH_INVALID,
        violations=[Violation(type=t) for t in types],
        repair_attempt=0,
        next_action=NextAction.PLANNER_REPAIR_RETRY,
    )


def test_success_returns_simple_summary() -> None:
    node = DeterministicUserFacingExplanation()
    out = node.run(run_id="r", validation_result=_success())
    assert isinstance(out, UserExplanation)
    assert out.detail == []


def test_failure_aggregates_translations_in_order() -> None:
    node = DeterministicUserFacingExplanation()
    out = node.run(
        run_id="r",
        validation_result=_failure(
            ViolationType.ORPHAN_DEPENDENCY,
            ViolationType.CYCLE_DETECTED,
        ),
    )
    assert "prerequisite" in out.detail[0].lower()
    assert "loop" in out.detail[1].lower() or "cycle" in out.detail[1].lower()


def test_duplicate_violation_types_deduped() -> None:
    node = DeterministicUserFacingExplanation()
    out = node.run(
        run_id="r",
        validation_result=_failure(
            ViolationType.ORPHAN_DEPENDENCY,
            ViolationType.ORPHAN_DEPENDENCY,
        ),
    )
    assert len(out.detail) == 1
