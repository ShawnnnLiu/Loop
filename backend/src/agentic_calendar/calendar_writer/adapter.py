"""External calendar adapter Protocol and value types.

Per axiom 06 line 18, the Calendar Write Manager is the only writer to an
external calendar; the adapter is the seam that hides which external calendar
is in use (Google, Outlook, in-memory fake, etc.). The Protocol is sync
because Phase 1 is sync end-to-end; a future async adapter, if needed, can be
wrapped at this boundary.

Value types are frozen ``slots=True`` dataclasses so that adding optional
fields with defaults in a later phase is non-breaking (e.g., ``etag`` for
optimistic concurrency in a real Google Calendar adapter).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class ExternalEventHandle:
    """Returned by :meth:`ExternalCalendarAdapter.create_event`."""

    calendar_event_id: str
    target_calendar_id: str


@dataclass(frozen=True, slots=True)
class ExternalEventRecord:
    """Snapshot of an external calendar event as returned by read/query.

    ``metadata`` is the flattened ``extendedProperties.private`` dict per
    ``docs/specs/calendar-event-mapping.schema.md`` lines 53-68; the four
    canonical keys (``app``, ``run_id``, ``plan_version``, ``task_id``) are
    required on every event the system creates.
    """

    calendar_event_id: str
    target_calendar_id: str
    scheduled_start: datetime
    scheduled_end: datetime
    metadata: Mapping[str, str]
    summary: str | None = None
    """Populated only by fakes for test observability. The Google adapter
    never ingests titles on read-back — raw calendar titles are never read
    back or stored (inbound privacy rule, axiom 06)."""


@runtime_checkable
class ExternalCalendarAdapter(Protocol):
    """Sync write/read surface against an external calendar.

    ``create_event``'s ``title`` is the task's human-readable title from the
    validated plan; ``None`` means the adapter applies its own generic
    fallback. Descriptions are never written.
    """

    def create_event(
        self,
        *,
        target_calendar_id: str,
        scheduled_start: datetime,
        scheduled_end: datetime,
        metadata: Mapping[str, str],
        title: str | None = None,
    ) -> ExternalEventHandle: ...

    def read_event(
        self,
        *,
        target_calendar_id: str,
        calendar_event_id: str,
    ) -> ExternalEventRecord | None: ...

    def delete_event(
        self,
        *,
        target_calendar_id: str,
        calendar_event_id: str,
    ) -> None: ...

    def query_events_by_metadata(
        self,
        *,
        target_calendar_id: str,
        run_id: str,
    ) -> list[ExternalEventRecord]: ...
