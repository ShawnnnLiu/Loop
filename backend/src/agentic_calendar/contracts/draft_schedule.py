"""``draft_schedule`` contract.

Canonical spec: ``docs/specs/draft-schedule.schema.md``.

A draft schedule is the minimal, hashable artifact derived from a
:class:`SchedulerOutput` that represents exactly what the user is asked to
approve. It carries only the fields whose values must be locked at approval
time so the recomputed hash at write time can prove the payload has not
drifted (axiom 06 lines 149-166).

A draft is **not** a wrapper around ``SchedulerOutput``; it's a distinct
contract. ``SchedulerOutput`` carries diagnostic fields (``repair_options``,
``available_capacity_min``, ``unscheduled_tasks``, etc.) that the UI may show
but that must not be part of the approval hash. Hashing only this draft
prevents accidental hash drift if ``SchedulerOutput`` grows new fields.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .scheduler_output import CalendarEventStatus, SchedulerOutput, ScheduleStatus


class DraftScheduleEntry(BaseModel):
    """One placed task as the user will see it for approval."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    task_id: str = Field(min_length=1)
    start: datetime
    end: datetime
    calendar_event_status: CalendarEventStatus = CalendarEventStatus.DRAFT_ONLY

    @model_validator(mode="after")
    def _times_make_sense(self) -> DraftScheduleEntry:
        if self.start.tzinfo is None or self.end.tzinfo is None:
            raise ValueError("draft schedule entry start/end must be timezone-aware")
        if self.end <= self.start:
            raise ValueError("draft schedule entry end must be strictly after start")
        return self


class DraftSchedule(BaseModel):
    """Immutable, hashable draft schedule.

    Order of ``entries`` is significant: axiom 06 line 153 calls it the
    "scheduled order" and the canonical hash covers this order.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    draft_schedule_id: str = Field(min_length=1)
    plan_version: str = Field(min_length=1)
    entries: tuple[DraftScheduleEntry, ...]
    created_at: datetime

    @model_validator(mode="after")
    def _created_at_tz_aware(self) -> DraftSchedule:
        if self.created_at.tzinfo is None:
            raise ValueError("draft schedule created_at must be timezone-aware")
        return self

    @model_validator(mode="after")
    def _entries_non_empty(self) -> DraftSchedule:
        if not self.entries:
            raise ValueError("draft schedule must contain at least one entry")
        return self

    @model_validator(mode="after")
    def _task_ids_unique(self) -> DraftSchedule:
        seen: set[str] = set()
        for entry in self.entries:
            if entry.task_id in seen:
                raise ValueError(
                    f"task_id {entry.task_id!r} appears more than once in draft entries"
                )
            seen.add(entry.task_id)
        return self

    @classmethod
    def from_scheduler_output(
        cls,
        output: SchedulerOutput,
        *,
        draft_schedule_id: str,
        created_at: datetime,
    ) -> DraftSchedule:
        """Derive a draft from a scheduler output, preserving scheduled order.

        Rejects ``output.schedule_status == FAILED`` — a failed scheduler run
        has no approvable draft.
        """
        if output.schedule_status is ScheduleStatus.FAILED:
            raise ValueError(
                "cannot build a draft schedule from a failed scheduler output"
            )
        entries = tuple(
            DraftScheduleEntry(
                task_id=st.task_id,
                start=st.start,
                end=st.end,
                calendar_event_status=st.calendar_event_status,
            )
            for st in output.scheduled_tasks
        )
        return cls(
            draft_schedule_id=draft_schedule_id,
            plan_version=output.plan_version,
            entries=entries,
            created_at=created_at,
        )

    def with_adjustments(
        self,
        new_starts: Mapping[str, datetime],
        *,
        draft_schedule_id: str,
        created_at: datetime,
    ) -> DraftSchedule:
        """Return a revised draft with the named tasks moved to new start times.

        ``new_starts`` maps ``task_id`` to its new (timezone-aware) start. For
        each moved task the new ``end`` is ``new_start + (old_end - old_start)``
        — duration is **preserved**, so a move can change *when* a block runs but
        never its length. A task absent from ``new_starts`` keeps its placement,
        and **entry order is preserved** for every task. The ``plan_version`` is
        unchanged (repositioning does not alter plan content); the caller supplies
        a fresh ``draft_schedule_id`` because drafts are immutable.

        Raises ``ValueError`` if ``new_starts`` references a ``task_id`` not in
        this draft — a caller cannot move a task that is not already present.
        Structural invariants are re-checked by the constructor.
        """
        known = {entry.task_id for entry in self.entries}
        unknown = sorted(tid for tid in new_starts if tid not in known)
        if unknown:
            raise ValueError(
                f"adjustment references unknown task_id(s): {unknown}"
            )
        revised = tuple(
            DraftScheduleEntry(
                task_id=entry.task_id,
                start=new_starts[entry.task_id],
                end=new_starts[entry.task_id] + (entry.end - entry.start),
                calendar_event_status=entry.calendar_event_status,
            )
            if entry.task_id in new_starts
            else entry
            for entry in self.entries
        )
        return DraftSchedule(
            draft_schedule_id=draft_schedule_id,
            plan_version=self.plan_version,
            entries=revised,
            created_at=created_at,
        )
