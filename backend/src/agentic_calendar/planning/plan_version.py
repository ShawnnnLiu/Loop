"""Immutable ``PlanVersion`` record (axiom 15).

The active plan is never mutated in place. New work creates a new
``PlanVersion`` and an approval flow promotes a draft to active. Phase 1
implements only the structural side of versioning: the model + lifecycle
states + append-only generation history. Approval / promotion semantics
land in Phase 2 alongside the calendar write path.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from agentic_calendar.contracts.task_plan import TaskPlan


class LifecycleState(StrEnum):
    """States a ``PlanVersion`` may move through.

    Phase 1 only writes ``DRAFT`` and ``DISCARDED``; ``APPROVED`` and
    ``ACTIVE`` arrive in Phase 2 with the approval gate.
    """

    DRAFT = "draft"
    APPROVED = "approved"
    ACTIVE = "active"
    DISCARDED = "discarded"


class GenerationStep(StrEnum):
    """The kind of step recorded in ``generation_history``."""

    STRATEGIST = "strategist"
    PLANNER = "planner"
    REPAIR = "repair"
    VALIDATION = "validation"
    SCHEDULER = "scheduler"
    NOTE = "note"


class GenerationStepRecord(BaseModel):
    """One append-only entry on a plan version's generation log."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    step: GenerationStep
    occurred_at: datetime
    detail: str = ""

    @model_validator(mode="after")
    def _aware(self) -> GenerationStepRecord:
        if self.occurred_at.tzinfo is None:
            raise ValueError("occurred_at must be timezone-aware")
        return self


class PlanVersion(BaseModel):
    """An immutable, versioned plan record.

    Use ``PlanVersion.append_history`` to produce a new instance with an
    extra step appended; never mutate ``generation_history`` directly.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    plan_version: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    parent_plan_version: str | None = None
    state: LifecycleState
    plan: TaskPlan
    generation_history: list[GenerationStepRecord] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def _timestamps_aware(self) -> PlanVersion:
        if self.created_at.tzinfo is None or self.updated_at.tzinfo is None:
            raise ValueError("created_at and updated_at must be timezone-aware")
        if self.updated_at < self.created_at:
            raise ValueError("updated_at must not precede created_at")
        return self

    @model_validator(mode="after")
    def _plan_version_matches(self) -> PlanVersion:
        if self.plan.plan_version != self.plan_version:
            raise ValueError(
                f"PlanVersion.plan_version ({self.plan_version!r}) must match "
                f"plan.plan_version ({self.plan.plan_version!r})"
            )
        return self

    def append_history(
        self, record: GenerationStepRecord, *, now: datetime
    ) -> PlanVersion:
        """Return a new ``PlanVersion`` with ``record`` appended.

        ``updated_at`` is bumped to ``now``. The original instance is left
        untouched (axiom 15: append-only).
        """
        return self.model_copy(
            update={
                "generation_history": [*self.generation_history, record],
                "updated_at": now,
            }
        )

    def transition_to(
        self, new_state: LifecycleState, *, now: datetime
    ) -> PlanVersion:
        """Return a new ``PlanVersion`` in ``new_state``.

        Allowed transitions (Phase 1):

        * ``DRAFT`` → ``APPROVED`` | ``DISCARDED``
        * ``APPROVED`` → ``ACTIVE`` | ``DISCARDED``
        * ``ACTIVE`` → ``DISCARDED``

        Other transitions raise ``ValueError`` because the lifecycle is the
        single source of truth for "may this plan be promoted?".
        """
        allowed: dict[LifecycleState, set[LifecycleState]] = {
            LifecycleState.DRAFT: {
                LifecycleState.APPROVED,
                LifecycleState.DISCARDED,
            },
            LifecycleState.APPROVED: {
                LifecycleState.ACTIVE,
                LifecycleState.DISCARDED,
            },
            LifecycleState.ACTIVE: {LifecycleState.DISCARDED},
            LifecycleState.DISCARDED: set(),
        }
        if new_state not in allowed[self.state]:
            raise ValueError(
                f"forbidden lifecycle transition {self.state.value} -> {new_state.value}"
            )
        return self.model_copy(update={"state": new_state, "updated_at": now})
