"""``validation_result`` contract.

Canonical spec: ``docs/specs/validation-result.schema.md``.

The Validation Layer always returns one of these. Producers must:

* set ``valid=False`` ⇒ a typed ``reason_code`` and at least one violation;
* set ``valid=True`` ⇒ no violations and a benign ``next_action``;
* never exceed ``max_repair_attempts`` (=2) for LLM-generated artifacts.

These invariants are enforced as model validators so a bug in the Validation
Layer cannot fabricate a misshapen result that downstream code would trust.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .reason_codes import ReasonCode
from .violation_types import ViolationType

MAX_REPAIR_ATTEMPTS_LLM = 2
"""Hard cap on LLM-artifact repair attempts (axiom 04)."""


class NextAction(StrEnum):
    """Deterministic next step after a validation result."""

    SCHEDULER = "scheduler"
    PLANNER_REPAIR_RETRY = "planner_repair_retry"
    STRATEGIST_REPAIR_RETRY = "strategist_repair_retry"
    ERROR_REQUIRES_USER = "error_requires_user"
    NOOP = "noop"


class ArtifactType(StrEnum):
    """The kind of artifact a ``ValidationResult`` describes."""

    USER_PROFILE = "user_profile"
    MOTIVATION_PROFILE = "motivation_profile"
    SYLLABUS_UNITS = "syllabus_units"
    TASK_PLAN = "task_plan"


class Violation(BaseModel):
    """One structured failure inside a ``ValidationResult``.

    The shape carries a typed ``type`` plus arbitrary ``details`` so each
    checker can attach the fields needed to repair the failure (e.g.
    ``invalid_dependency`` for ``orphan_dependency``). Detail fields are
    intentionally loose because ``ViolationType`` is the contract surface;
    every checker documents what it puts in ``details`` next to its code.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: ViolationType
    task_id: str | None = None
    module_id: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class ValidationResult(BaseModel):
    """Deterministic pass/fail with typed reason and structured violations."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str = Field(min_length=1)
    artifact_type: ArtifactType
    valid: bool
    repairable: bool
    reason_code: ReasonCode | None = None
    violations: list[Violation] = Field(default_factory=list)
    repair_attempt: int = Field(ge=0)
    max_repair_attempts: int = Field(default=MAX_REPAIR_ATTEMPTS_LLM, ge=0, le=10)
    next_action: NextAction

    @model_validator(mode="after")
    def _failure_must_have_reason_and_violations(self) -> ValidationResult:
        if not self.valid:
            if self.reason_code is None:
                raise ValueError(
                    "ValidationResult.valid=False requires a typed reason_code"
                )
            if not self.violations:
                raise ValueError(
                    "ValidationResult.valid=False requires at least one violation"
                )
        return self

    @model_validator(mode="after")
    def _success_carries_no_violations(self) -> ValidationResult:
        if self.valid:
            if self.violations:
                raise ValueError(
                    "ValidationResult.valid=True must carry zero violations"
                )
            if self.reason_code is not None:
                raise ValueError(
                    "ValidationResult.valid=True must not carry a reason_code"
                )
        return self

    @model_validator(mode="after")
    def _attempt_within_cap(self) -> ValidationResult:
        if self.repair_attempt > self.max_repair_attempts:
            raise ValueError(
                f"repair_attempt ({self.repair_attempt}) exceeds "
                f"max_repair_attempts ({self.max_repair_attempts})"
            )
        return self
