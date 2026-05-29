"""``calendar_event_mapping`` contract.

Canonical spec: ``docs/specs/calendar-event-mapping.schema.md``.

Local mapping between an internal task and the external calendar event the
system created on the user's behalf. Verification, duplicate prevention, and
rollback all rely on this mapping.

Unlike the immutable contracts in this package, ``CalendarEventMapping`` is
**not** ``frozen=True`` — the ``calendar_write_status`` and ``last_verified_at``
fields change as a write progresses (e.g., ``dry_run`` → ``written`` →
``verified``). The model still forbids unknown fields and re-runs invariants
on any ``model_copy(update=...)``. Status-transition legality is enforced by
``CalendarEventMappingStore``; this model only enforces single-record
invariants.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CalendarWriteStatus(StrEnum):
    """Lifecycle of a single external calendar event (spec lines 43-51)."""

    DRY_RUN = "dry_run"
    WRITTEN = "written"
    VERIFIED = "verified"
    VERIFICATION_FAILED = "verification_failed"
    ROLLBACK_PENDING = "rollback_pending"
    ROLLED_BACK = "rolled_back"
    ROLLBACK_FAILED = "rollback_failed"


class CalendarEventMapping(BaseModel):
    """One internal task ↔ one external calendar event."""

    model_config = ConfigDict(extra="forbid")

    task_id: str = Field(min_length=1)
    plan_version: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    calendar_event_id: str | None
    scheduled_start: datetime
    scheduled_end: datetime
    calendar_write_status: CalendarWriteStatus
    user_modified_bool: bool
    last_verified_at: datetime | None

    @model_validator(mode="after")
    def _times_tz_aware(self) -> CalendarEventMapping:
        if self.scheduled_start.tzinfo is None or self.scheduled_end.tzinfo is None:
            raise ValueError(
                "calendar event mapping scheduled_start/scheduled_end must be timezone-aware"
            )
        if (
            self.last_verified_at is not None
            and self.last_verified_at.tzinfo is None
        ):
            raise ValueError(
                "calendar event mapping last_verified_at must be timezone-aware"
            )
        return self

    @model_validator(mode="after")
    def _start_before_end(self) -> CalendarEventMapping:
        if self.scheduled_end <= self.scheduled_start:
            raise ValueError(
                "calendar event mapping scheduled_end must be strictly after scheduled_start"
            )
        return self

    @model_validator(mode="after")
    def _verified_requires_event_id(self) -> CalendarEventMapping:
        if (
            self.calendar_write_status is CalendarWriteStatus.VERIFIED
            and self.calendar_event_id is None
        ):
            raise ValueError(
                "calendar_write_status='verified' requires a non-null calendar_event_id"
            )
        return self

    def with_status(
        self,
        new_status: CalendarWriteStatus,
        *,
        now: datetime,
        calendar_event_id: str | None = None,
    ) -> CalendarEventMapping:
        """Return a copy with an updated status (re-runs all validators).

        ``calendar_event_id`` is updated only when the caller supplies it
        (i.e., the first transition from ``dry_run`` to ``written``); otherwise
        the existing value is preserved.

        Status-transition legality is enforced by
        ``CalendarEventMappingStore.update_status``, not here. Field
        invariants (``verified`` requires non-null event id, etc.) ARE
        enforced — ``model_copy`` does not re-run validators in Pydantic v2,
        so we rebuild via ``model_validate``.
        """
        payload: dict[str, object] = self.model_dump(mode="python")
        payload["calendar_write_status"] = new_status
        payload["last_verified_at"] = now
        if calendar_event_id is not None:
            payload["calendar_event_id"] = calendar_event_id
        return CalendarEventMapping.model_validate(payload)
