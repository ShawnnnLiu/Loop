"""Real Google Calendar adapter (Phase 9c).

Implements :class:`~agentic_calendar.calendar_writer.adapter.ExternalCalendarAdapter`
against the Google Calendar v3 API. The Calendar Write Manager remains the
only caller (axiom 06); every axiom 06 invariant — dry-run, duplicate
detection by ``run_id`` metadata, verification read-back, rollback via
``calendar_event_mapping``, the ``approved_payload_hash`` recheck — lives in
the manager and works unchanged through this adapter.

Two safety properties are enforced *here*:

* **Dedicated calendar only.** The adapter is constructed with the one
  secondary calendar id it may touch; any call addressed elsewhere (including
  ``primary``) raises before any network I/O. The system can therefore never
  write into the user's primary calendar, whatever the caller passes.
* **Outbound titles only, inbound never.** Created events carry the task's
  title as the summary (user-approved posture change, 2026-07-16 — the
  events land on the user's own dedicated calendar) and the four canonical
  metadata keys (``app``/``run_id``/``plan_version``/``task_id``) in
  ``extendedProperties.private``. Descriptions are never written, and
  inbound titles are still never read back or stored (axiom 06): read-back
  ingests times and metadata only.

The Google SDK stays at the edge: credentials and the ``service`` object are
built in ``tools/`` (the only place allowed to import ``google.*``; see the
boundary grep test) and injected here through
:class:`GoogleApiHttpTransport`, which references only ``googleapiclient``
for error translation — lazily, so importing this module never requires the
dependency. Tests fake :class:`GoogleCalendarTransport` with real-shape API
payloads and never touch the network.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, Protocol, runtime_checkable

from .adapter import ExternalEventHandle, ExternalEventRecord
from .errors import CalendarWriterError
from .metadata import APP_TAG

EVENT_SUMMARY = "Career prep study block"
"""Fallback summary when the caller supplies no task title."""

_MAX_SUMMARY_LEN = 1024
"""Practical cap on a Google Calendar event summary."""


class GoogleCalendarAdapterError(CalendarWriterError):
    """Base for Google-adapter errors that callers may catch.

    Subclasses :class:`CalendarWriterError` so that every adapter failure
    raised inside the manager's write path is caught by the manager's
    boundary translation (``CalendarWriteManager._translate_error``) and
    becomes a typed ``WriteResult`` with the lock released — an adapter
    fault must never escape the manager as a raw exception and strand a run
    mid-state (axiom 06/16). Inherits the base's
    ``ReasonCode.CALENDAR_WRITE_FAILED``.
    """


class DedicatedCalendarViolationError(GoogleCalendarAdapterError):
    """A call addressed a calendar other than the dedicated secondary one."""

    def __init__(self, *, requested: str, dedicated: str) -> None:
        self.requested = requested
        self.dedicated = dedicated
        super().__init__(
            f"refusing to touch calendar {requested!r}: this adapter is bound "
            f"to the dedicated secondary calendar {dedicated!r}"
        )


class GoogleCalendarApiError(GoogleCalendarAdapterError):
    """A Google API call failed in a way that is not 'event absent'."""

    def __init__(self, message: str, *, status: int | None = None) -> None:
        self.status = status
        super().__init__(message)


@runtime_checkable
class GoogleCalendarTransport(Protocol):
    """Dict-in/dict-out seam over the Calendar v3 events surface.

    Implementations translate provider errors: 404/410 become ``None`` (get)
    or a silent no-op (delete) — the same absent-event semantics as the
    in-memory adapter — and anything else raises
    :class:`GoogleCalendarApiError`. Payload dicts use the wire shape of the
    Calendar v3 ``Event`` resource so recorded/fake transports stay
    real-shape.
    """

    def insert_event(
        self, *, calendar_id: str, body: Mapping[str, Any]
    ) -> Mapping[str, Any]: ...

    def get_event(
        self, *, calendar_id: str, event_id: str
    ) -> Mapping[str, Any] | None: ...

    def delete_event(self, *, calendar_id: str, event_id: str) -> None: ...

    def list_events(
        self, *, calendar_id: str, private_properties: Mapping[str, str]
    ) -> list[Mapping[str, Any]]: ...


class GoogleApiHttpTransport:
    """Live transport over an injected, already-authorized ``service``.

    ``service`` is the ``googleapiclient`` resource built by
    ``tools/google_calendar_auth.py`` (the OAuth flow and every ``google.*``
    import live there). It is typed ``Any`` deliberately: the discovery
    client is dynamically generated and this region must not import the SDK
    at module scope.
    """

    def __init__(self, service: Any) -> None:
        self._service = service

    @staticmethod
    def _absent_status(exc: Exception) -> int | None:
        """Status code if ``exc`` is an HttpError, else ``None`` (re-raise)."""
        try:
            from googleapiclient.errors import HttpError
        except ImportError:  # pragma: no cover - dependency is installed in dev
            return None
        if isinstance(exc, HttpError):
            return int(exc.resp.status)
        return None

    @staticmethod
    def _error_detail(exc: Exception) -> str:
        """Provider-side failure detail to append to a raised message.

        Carries only the HTTP status and Google's error prose (or the
        exception type + text for non-HTTP failures) — calendar ids and
        provider prose, never secrets. Truncated so a giant provider payload
        cannot bloat logs or results.
        """
        try:
            from googleapiclient.errors import HttpError
        except ImportError:  # pragma: no cover - dependency is installed in dev
            pass
        else:
            if isinstance(exc, HttpError):
                detail = exc.reason or str(exc)[:200]
                return f"HTTP {int(exc.resp.status)}: {detail}"
        return f"{type(exc).__name__}: {str(exc)[:200]}"

    def insert_event(
        self, *, calendar_id: str, body: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        try:
            result: Mapping[str, Any] = (
                self._service.events()
                .insert(calendarId=calendar_id, body=dict(body))
                .execute()
            )
            return result
        except Exception as exc:
            status = self._absent_status(exc)
            raise GoogleCalendarApiError(
                f"events.insert failed for calendar {calendar_id!r}: "
                f"{self._error_detail(exc)}",
                status=status,
            ) from exc

    def get_event(
        self, *, calendar_id: str, event_id: str
    ) -> Mapping[str, Any] | None:
        try:
            result: Mapping[str, Any] = (
                self._service.events()
                .get(calendarId=calendar_id, eventId=event_id)
                .execute()
            )
            return result
        except Exception as exc:
            status = self._absent_status(exc)
            if status in (404, 410):
                return None
            raise GoogleCalendarApiError(
                f"events.get failed for event {event_id!r}: "
                f"{self._error_detail(exc)}",
                status=status,
            ) from exc

    def delete_event(self, *, calendar_id: str, event_id: str) -> None:
        try:
            self._service.events().delete(
                calendarId=calendar_id, eventId=event_id
            ).execute()
        except Exception as exc:
            status = self._absent_status(exc)
            if status in (404, 410):
                return  # idempotent, like the in-memory adapter
            raise GoogleCalendarApiError(
                f"events.delete failed for event {event_id!r}: "
                f"{self._error_detail(exc)}",
                status=status,
            ) from exc

    def list_events(
        self, *, calendar_id: str, private_properties: Mapping[str, str]
    ) -> list[Mapping[str, Any]]:
        properties = [f"{key}={value}" for key, value in sorted(private_properties.items())]
        items: list[Mapping[str, Any]] = []
        page_token: str | None = None
        try:
            while True:
                response = (
                    self._service.events()
                    .list(
                        calendarId=calendar_id,
                        privateExtendedProperty=properties,
                        singleEvents=True,
                        maxResults=2500,
                        pageToken=page_token,
                    )
                    .execute()
                )
                items.extend(response.get("items", []))
                page_token = response.get("nextPageToken")
                if not page_token:
                    return items
        except Exception as exc:
            status = self._absent_status(exc)
            raise GoogleCalendarApiError(
                f"events.list failed for calendar {calendar_id!r}: "
                f"{self._error_detail(exc)}",
                status=status,
            ) from exc

    def query_free_busy(
        self, *, calendar_id: str, time_min: datetime, time_max: datetime
    ) -> list[tuple[datetime, datetime]]:
        """Busy intervals on ``calendar_id`` within ``[time_min, time_max)``.

        Uses ``freebusy.query`` so only opaque busy *ranges* cross the boundary —
        never event titles or descriptions (privacy axiom). Read-only, so unlike
        the write path it may target any calendar, including the user's
        ``primary``.
        """
        body = {
            "timeMin": time_min.isoformat(),
            "timeMax": time_max.isoformat(),
            "items": [{"id": calendar_id}],
        }
        try:
            response: Mapping[str, Any] = (
                self._service.freebusy().query(body=body).execute()
            )
        except Exception as exc:
            status = self._absent_status(exc)
            raise GoogleCalendarApiError(
                f"freebusy.query failed for calendar {calendar_id!r}: "
                f"{self._error_detail(exc)}",
                status=status,
            ) from exc
        windows = response.get("calendars", {}).get(calendar_id, {}).get("busy", [])
        return [
            (_free_busy_time(w, "start"), _free_busy_time(w, "end")) for w in windows
        ]


def _free_busy_time(window: Mapping[str, Any], key: str) -> datetime:
    """Parse one RFC3339 free/busy bound into a timezone-aware datetime."""
    raw = window.get(key)
    if not isinstance(raw, str):
        raise GoogleCalendarApiError(f"free/busy window missing {key!r}: {window!r}")
    return datetime.fromisoformat(raw.replace("Z", "+00:00"))


def _event_time(item: Mapping[str, Any], key: str, event_id: str) -> datetime:
    """Parse one RFC3339 ``dateTime`` bound; all-day events are foreign here.

    The system only ever creates timed events; an event without a
    ``dateTime`` was not created by us and must fail loudly rather than be
    silently coerced.
    """
    raw = item.get(key, {}).get("dateTime")
    if not isinstance(raw, str):
        raise GoogleCalendarApiError(
            f"event {event_id!r} has no {key}.dateTime (all-day or malformed)"
        )
    return datetime.fromisoformat(raw.replace("Z", "+00:00"))


class GoogleCalendarAdapter:
    """Google-backed :class:`ExternalCalendarAdapter`, bound to one calendar."""

    def __init__(
        self, *, transport: GoogleCalendarTransport, dedicated_calendar_id: str
    ) -> None:
        if not dedicated_calendar_id or dedicated_calendar_id == "primary":
            raise DedicatedCalendarViolationError(
                requested=dedicated_calendar_id, dedicated="<a secondary calendar>"
            )
        self._transport = transport
        self._dedicated = dedicated_calendar_id

    def _guard(self, target_calendar_id: str) -> None:
        if target_calendar_id != self._dedicated:
            raise DedicatedCalendarViolationError(
                requested=target_calendar_id, dedicated=self._dedicated
            )

    def create_event(
        self,
        *,
        target_calendar_id: str,
        scheduled_start: datetime,
        scheduled_end: datetime,
        metadata: Mapping[str, str],
        title: str | None = None,
    ) -> ExternalEventHandle:
        self._guard(target_calendar_id)
        body = {
            # Strip, then cap, then fall back — a whitespace-only title must
            # hit the generic fallback, not produce an empty summary.
            "summary": (title or "").strip()[:_MAX_SUMMARY_LEN] or EVENT_SUMMARY,
            "start": {
                "dateTime": scheduled_start.astimezone(UTC).isoformat(),
                "timeZone": "UTC",
            },
            "end": {
                "dateTime": scheduled_end.astimezone(UTC).isoformat(),
                "timeZone": "UTC",
            },
            "extendedProperties": {"private": dict(metadata)},
        }
        created = self._transport.insert_event(
            calendar_id=target_calendar_id, body=body
        )
        event_id = created.get("id")
        if not isinstance(event_id, str) or not event_id:
            raise GoogleCalendarApiError("events.insert returned no event id")
        return ExternalEventHandle(
            calendar_event_id=event_id, target_calendar_id=target_calendar_id
        )

    def read_event(
        self,
        *,
        target_calendar_id: str,
        calendar_event_id: str,
    ) -> ExternalEventRecord | None:
        self._guard(target_calendar_id)
        item = self._transport.get_event(
            calendar_id=target_calendar_id, event_id=calendar_event_id
        )
        # Google soft-deletes: a deleted event reads back with
        # status=cancelled. For verification/rollback semantics that IS
        # "absent" — matching the in-memory adapter's None.
        if item is None or item.get("status") == "cancelled":
            return None
        return self._to_record(item, target_calendar_id)

    def delete_event(
        self,
        *,
        target_calendar_id: str,
        calendar_event_id: str,
    ) -> None:
        self._guard(target_calendar_id)
        self._transport.delete_event(
            calendar_id=target_calendar_id, event_id=calendar_event_id
        )

    def query_events_by_metadata(
        self,
        *,
        target_calendar_id: str,
        run_id: str,
    ) -> list[ExternalEventRecord]:
        self._guard(target_calendar_id)
        items = self._transport.list_events(
            calendar_id=target_calendar_id,
            private_properties={"app": APP_TAG, "run_id": run_id},
        )
        return [
            self._to_record(item, target_calendar_id)
            for item in items
            if item.get("status") != "cancelled"
        ]

    def _to_record(
        self, item: Mapping[str, Any], target_calendar_id: str
    ) -> ExternalEventRecord:
        event_id = item.get("id")
        if not isinstance(event_id, str) or not event_id:
            raise GoogleCalendarApiError("event resource has no id")
        private = item.get("extendedProperties", {}).get("private", {})
        # ``summary`` is intentionally not ingested: inbound titles are never
        # read back or stored (axiom 06 privacy rule).
        return ExternalEventRecord(
            calendar_event_id=event_id,
            target_calendar_id=target_calendar_id,
            scheduled_start=_event_time(item, "start", event_id),
            scheduled_end=_event_time(item, "end", event_id),
            metadata={str(k): str(v) for k, v in private.items()},
        )
