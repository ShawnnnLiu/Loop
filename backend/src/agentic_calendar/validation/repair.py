"""Structured repair payload (axiom 04).

When validation fails *and* a repair attempt is allowed, the orchestrator
hands a ``RepairPayload`` back to the calling Planner. The repair loop is
hard-capped at 2 attempts; after the second failure the next action becomes
``ERROR_REQUIRES_USER`` (axiom 04 + axiom 16).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from agentic_calendar.contracts.validation_result import (
    MAX_REPAIR_ATTEMPTS_LLM,
    ArtifactType,
    NextAction,
    Violation,
)


class RepairPayload(BaseModel):
    """Hand-off envelope sent to the Planner for one repair attempt."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    repair_reason: str = "validation_failed"
    artifact_type: ArtifactType
    attempt: int = Field(ge=1, le=MAX_REPAIR_ATTEMPTS_LLM)
    max_attempts: int = Field(default=MAX_REPAIR_ATTEMPTS_LLM, ge=1, le=10)
    violations: list[Violation] = Field(min_length=1)


def next_action_for(*, valid: bool, repair_attempt: int, repairable: bool) -> NextAction:
    """Decide the deterministic next step for a validation outcome.

    The mapping is:

    * ``valid=True``                                       → ``SCHEDULER``
    * ``valid=False`` and ``repair_attempt < 2`` and repairable
      → ``PLANNER_REPAIR_RETRY``
    * otherwise                                            → ``ERROR_REQUIRES_USER``
    """
    if valid:
        return NextAction.SCHEDULER
    if repairable and repair_attempt < MAX_REPAIR_ATTEMPTS_LLM:
        return NextAction.PLANNER_REPAIR_RETRY
    return NextAction.ERROR_REQUIRES_USER
