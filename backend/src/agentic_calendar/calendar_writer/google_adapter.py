"""Raise-only placeholder for the real Google Calendar adapter.

Phase 2 ships the seam only. A later phase will implement the four Protocol
methods against ``google-api-python-client`` (or equivalent). Until then,
every call raises :class:`NotImplementedError`. Importing this module today
must not pull in any Google SDK; only stdlib + sibling :mod:`adapter`
imports are allowed.

This stub satisfies :class:`ExternalCalendarAdapter` at the runtime-checkable
Protocol level (every method is present with the right shape) so callers can
wire it into dependency-injection scaffolding without conditional imports;
the calls just fail loudly.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime

from .adapter import ExternalEventHandle, ExternalEventRecord


class GoogleCalendarAdapter:
    """Placeholder Google Calendar adapter.

    Replace with a real implementation in a later phase. Until then, treat
    this class as a marker; do not register it in production wiring.
    """

    _NOT_IMPLEMENTED = (
        "GoogleCalendarAdapter is a placeholder; the real Google Calendar "
        "adapter ships in a later phase."
    )

    def create_event(
        self,
        *,
        target_calendar_id: str,
        scheduled_start: datetime,
        scheduled_end: datetime,
        metadata: Mapping[str, str],
    ) -> ExternalEventHandle:
        raise NotImplementedError(self._NOT_IMPLEMENTED)

    def read_event(
        self,
        *,
        target_calendar_id: str,
        calendar_event_id: str,
    ) -> ExternalEventRecord | None:
        raise NotImplementedError(self._NOT_IMPLEMENTED)

    def delete_event(
        self,
        *,
        target_calendar_id: str,
        calendar_event_id: str,
    ) -> None:
        raise NotImplementedError(self._NOT_IMPLEMENTED)

    def query_events_by_metadata(
        self,
        *,
        target_calendar_id: str,
        run_id: str,
    ) -> list[ExternalEventRecord]:
        raise NotImplementedError(self._NOT_IMPLEMENTED)
