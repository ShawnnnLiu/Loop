"""``task_disposition`` contract.

Canonical spec: ``docs/specs/task-disposition.schema.md`` (ADR-0008; axioms 05,
11, 20).

A :class:`TaskDispositionRecord` is the append-only, durable memory of what a
user has completed or dropped (``skipped`` is a reserved disposition with no
producer yet — see :class:`TaskDispositionType`). It feeds the scheduler
projection
(``SchedulerInput.completed_task_ids``) and the completion-relative
drag-to-adjust advisory check (ADR-0008). The store decides nothing with an
LLM; code records a disposition from a completion signal or an explicit drop
intent.

``disposition_id`` uniqueness / dedup is a store concern, not a single-object
invariant (same split as ``telemetry`` / ``checkin_event``).
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .reason_codes import ReasonCode


class TaskDispositionType(StrEnum):
    """What became of a task."""

    COMPLETED = "completed"
    """The user completed the task (mirrored from telemetry; ``source: system``)."""
    SKIPPED = "skipped"
    """Reserved: an explicit skip-without-completing. No producer in the
    completion/drop feature; defined so the store / projection need no later
    enum change. Not yet part of the completed/dropped scheduler projection."""
    DROPPED = "dropped"
    """The user explicitly dropped an unfinished task (``source: user``)."""


class DispositionSource(StrEnum):
    """Who or what recorded the disposition."""

    USER = "user"
    """An explicit user action (a drop)."""
    SYSTEM = "system"
    """Derived deterministically from an observable signal (a telemetry
    completion)."""


class TaskDispositionRecord(BaseModel):
    """One append-only completion / skip / drop fact about a task."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    disposition_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    plan_version: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    disposition: TaskDispositionType
    reason_code: ReasonCode | None = None
    source: DispositionSource
    created_at: datetime

    @model_validator(mode="after")
    def _created_at_aware(self) -> TaskDispositionRecord:
        if self.created_at.tzinfo is None:
            raise ValueError("task disposition created_at must be timezone-aware")
        return self

    @model_validator(mode="after")
    def _reason_code_matches_disposition(self) -> TaskDispositionRecord:
        """``dropped`` requires a typed ``reason_code``; ``completed`` forbids
        one (task-disposition spec invariants). ``skipped`` leaves it optional."""
        if (
            self.disposition is TaskDispositionType.DROPPED
            and self.reason_code is None
        ):
            raise ValueError("a dropped disposition must carry a typed reason_code")
        if (
            self.disposition is TaskDispositionType.COMPLETED
            and self.reason_code is not None
        ):
            raise ValueError("a completed disposition must have a null reason_code")
        return self
