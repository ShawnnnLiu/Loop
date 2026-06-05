"""Append-only telemetry-event store (Phase 4).

Every task-execution outcome is one immutable :class:`TelemetryEvent`. The store
is append-only: a ``telemetry_event_id`` may be written exactly once
(telemetry-spec invariant "events are append-only and never silently mutated").
Reingestion is deduplicated by id — the ingestion layer checks :meth:`exists`
before appending so a retried client delivery is idempotent rather than an error.

The store indexes by ``task_id`` only. There is no ``user_id`` on a telemetry
event (the spec keeps the payload minimal); per-user aggregation is done by the
caller, which knows from the active plan which ``task_id`` values belong to a
user and passes that scoped list to metrics/calibration.
"""

from __future__ import annotations

import threading
from typing import Protocol, runtime_checkable

from agentic_calendar.common.errors import AgenticCalendarError
from agentic_calendar.contracts.telemetry import TelemetryEvent


class TelemetryEventStoreError(AgenticCalendarError):
    """Base for telemetry-event-store errors."""


class TelemetryEventAlreadyExistsError(TelemetryEventStoreError):
    """Attempted to append a ``telemetry_event_id`` that already exists."""


@runtime_checkable
class TelemetryEventStore(Protocol):
    """Append/read surface for telemetry events."""

    def append(self, event: TelemetryEvent) -> None: ...

    def exists(self, telemetry_event_id: str) -> bool: ...

    def get(self, telemetry_event_id: str) -> TelemetryEvent | None: ...

    def list_for_task(self, task_id: str) -> list[TelemetryEvent]: ...

    def all(self) -> list[TelemetryEvent]: ...


class InMemoryTelemetryEventStore:
    """Default Phase 4 store. Thread-safe, ephemeral, non-persistent."""

    def __init__(self) -> None:
        self._by_id: dict[str, TelemetryEvent] = {}
        self._order: list[str] = []
        self._lock = threading.RLock()

    def append(self, event: TelemetryEvent) -> None:
        """Append ``event``. Rejects a duplicate id (append-only)."""
        with self._lock:
            if event.telemetry_event_id in self._by_id:
                raise TelemetryEventAlreadyExistsError(event.telemetry_event_id)
            self._by_id[event.telemetry_event_id] = event
            self._order.append(event.telemetry_event_id)

    def exists(self, telemetry_event_id: str) -> bool:
        with self._lock:
            return telemetry_event_id in self._by_id

    def get(self, telemetry_event_id: str) -> TelemetryEvent | None:
        with self._lock:
            return self._by_id.get(telemetry_event_id)

    def list_for_task(self, task_id: str) -> list[TelemetryEvent]:
        with self._lock:
            return [self._by_id[i] for i in self._order if self._by_id[i].task_id == task_id]

    def all(self) -> list[TelemetryEvent]:
        """Return every event in insertion order."""
        with self._lock:
            return [self._by_id[i] for i in self._order]
