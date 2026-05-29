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
