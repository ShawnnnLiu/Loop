"""``task_disposition`` contract.

Canonical spec: ``docs/specs/task-disposition.schema.md`` (ADR-0008; axioms 05,
11, 20).

A :class:`TaskDispositionRecord` is the append-only, durable memory of what a
user has completed or dropped (``skipped`` is a reserved disposition with no
producer yet — see :class:`TaskDispositionType`), and of tasks whose calendar
event the user deleted externally (``event_deleted``, recorded by
reconciliation and surfaced by the read projections — never a completion). It
feeds the scheduler projection
(``SchedulerInput.completed_task_ids``) and the completion-relative
drag-to-adjust advisory check (ADR-0008). The store decides nothing with an
LLM; code records a disposition from a completion signal, an explicit drop
intent, or an observed external deletion.

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
    EVENT_DELETED = "event_deleted"
    """Reconciliation observed the task's calendar event deleted from the
    dedicated external calendar (``source: system``). Event memory, not task
    cancellation: the task stays planned (axiom 06 — delete-means-cancelled is
    opt-in, never default) and this value never joins the completed/dropped
    scheduler projection; it only feeds the read projections that surface the
    deletion."""


class DispositionSource(StrEnum):
    """Who or what recorded the disposition."""

    USER = "user"
    """An explicit user action (a drop)."""
    SYSTEM = "system"
    """Derived deterministically from an observable signal (a telemetry
    completion; a reconciliation-observed external deletion)."""


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
        """``dropped`` and ``event_deleted`` require a typed ``reason_code``;
        ``completed`` forbids one (task-disposition spec invariants). ``skipped``
        leaves it optional."""
        if (
            self.disposition is TaskDispositionType.DROPPED
            and self.reason_code is None
        ):
            raise ValueError("a dropped disposition must carry a typed reason_code")
        if (
            self.disposition is TaskDispositionType.EVENT_DELETED
            and self.reason_code is None
        ):
            raise ValueError(
                "an event_deleted disposition must carry a typed reason_code"
            )
        if (
            self.disposition is TaskDispositionType.COMPLETED
            and self.reason_code is not None
        ):
            raise ValueError("a completed disposition must have a null reason_code")
        return self
