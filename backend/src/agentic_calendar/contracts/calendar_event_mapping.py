"""``calendar_event_mapping`` contract.

Canonical spec: ``docs/specs/calendar-event-mapping.schema.md``.

Local mapping between an internal task and the external calendar event the
system created on the user's behalf. Verification, duplicate prevention, and
rollback all rely on this mapping.

Unlike the immutable contracts in this package, ``CalendarEventMapping`` is
**not** ``frozen=True`` — the ``calendar_write_status`` and ``last_verified_at``
fields change as a write progresses (e.g., ``dry_run`` → ``written`` →
``verified``). The model forbids unknown fields. Beware: Pydantic v2
``model_copy(update=...)`` does NOT re-run validators — use ``with_status()``
for all status transitions; it rebuilds via ``model_validate`` so the
single-record invariants are re-enforced. Status-transition legality is
enforced by ``CalendarEventMappingStore``; this model only enforces
single-record invariants.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CalendarWriteStatus(StrEnum):
    """Lifecycle of a single external calendar event (spec lines 43-51)."""

    DRY_RUN = "dry_run"
    """Reserved (axiom 06 dry-run requirement). **No current producer.**

    Today's dry-run surface is ``CalendarWriteManager.preview()``, which is
    pure and persists no mappings. Persisted ``dry_run`` mappings (an audit
    trail of exactly what a write *would* create, promotable to ``written``)
    land with the operator dry-run flow when a real external adapter ships;
    the ``dry_run -> written | rolled_back`` transitions are already speced
    and enforced by the store for that arrival."""

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

        ``last_verified_at`` is stamped to ``now`` only when ``new_status`` is
        a verification outcome (``VERIFIED`` or ``VERIFICATION_FAILED``); other
        transitions preserve the prior value. ``last_verified_at`` semantically
        means "the time the external event was last read back from the
        calendar," not "the time the row was last touched."

        Status-transition legality is enforced by
        ``CalendarEventMappingStore.update_status``, not here. Field
        invariants (``verified`` requires non-null event id, etc.) ARE
        enforced — ``model_copy`` does not re-run validators in Pydantic v2,
        so we rebuild via ``model_validate``.
        """
        payload: dict[str, object] = self.model_dump(mode="python")
        payload["calendar_write_status"] = new_status
        if new_status in (
            CalendarWriteStatus.VERIFIED,
            CalendarWriteStatus.VERIFICATION_FAILED,
        ):
            payload["last_verified_at"] = now
        if calendar_event_id is not None:
            payload["calendar_event_id"] = calendar_event_id
        return CalendarEventMapping.model_validate(payload)

    def with_external_edit(
        self,
        *,
        now: datetime,
        new_start: datetime | None = None,
        new_end: datetime | None = None,
    ) -> CalendarEventMapping:
        """Return a copy recording that the user edited this event directly on
        the external calendar (re-runs all validators).

        Always sets ``user_modified_bool=True`` and stamps ``last_verified_at``
        to ``now`` — inbound reconciliation read the event back from the
        calendar (calendar-reconciliation spec). When ``new_start``/``new_end``
        are supplied (an *adopted* move/resize) the scheduled times are updated
        to the calendar's truth; for a flagged (rejected / deleted) edit they
        are omitted and the prior internal time stays the system of record
        (axiom 06: the in-app schedule is authoritative).

        This is **not** a status transition: ``calendar_write_status`` and
        ``calendar_event_id`` are preserved, so the store does not run the
        legal-transition table for it. ``model_copy`` does not re-run validators
        in Pydantic v2, so we rebuild via ``model_validate``.
        """
        if (new_start is None) != (new_end is None):
            raise ValueError(
                "with_external_edit requires both new_start and new_end, or neither"
            )
        payload: dict[str, object] = self.model_dump(mode="python")
        payload["user_modified_bool"] = True
        payload["last_verified_at"] = now
        if new_start is not None and new_end is not None:
            payload["scheduled_start"] = new_start
            payload["scheduled_end"] = new_end
        return CalendarEventMapping.model_validate(payload)
