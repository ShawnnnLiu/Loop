"""Append-only check-in event store (Phase 7).

Every submitted weekly check-in is one immutable :class:`CheckinEvent`. The
store is append-only: a ``checkin_id`` may be written exactly once (axiom 21:
"check-in records are append-only"). Mirrors the telemetry event store's
protocol/in-memory split so a persistent backend can swap in later.
"""

from __future__ import annotations

import threading
from typing import Protocol, runtime_checkable

from agentic_calendar.common.errors import AgenticCalendarError
from agentic_calendar.contracts.checkin_event import CheckinEvent


class CheckinEventStoreError(AgenticCalendarError):
    """Base for check-in-event-store errors."""


class CheckinEventAlreadyExistsError(CheckinEventStoreError):
    """Attempted to append a ``checkin_id`` that already exists."""


@runtime_checkable
class CheckinEventStore(Protocol):
    """Append/read surface for check-in events."""

    def append(self, event: CheckinEvent) -> None: ...

    def exists(self, checkin_id: str) -> bool: ...

    def get(self, checkin_id: str) -> CheckinEvent | None: ...

    def list_for_plan(self, user_id: str, plan_id: str) -> list[CheckinEvent]: ...

    def all(self) -> list[CheckinEvent]: ...


class InMemoryCheckinEventStore:
    """Default Phase 7 store. Thread-safe, ephemeral, non-persistent."""

    def __init__(self) -> None:
        self._by_id: dict[str, CheckinEvent] = {}
        self._order: list[str] = []
        self._lock = threading.RLock()

    def append(self, event: CheckinEvent) -> None:
        """Append ``event``. Rejects a duplicate id (append-only)."""
        with self._lock:
            if event.checkin_id in self._by_id:
                raise CheckinEventAlreadyExistsError(event.checkin_id)
            self._by_id[event.checkin_id] = event
            self._order.append(event.checkin_id)

    def exists(self, checkin_id: str) -> bool:
        with self._lock:
            return checkin_id in self._by_id

    def get(self, checkin_id: str) -> CheckinEvent | None:
        with self._lock:
            return self._by_id.get(checkin_id)

    def list_for_plan(self, user_id: str, plan_id: str) -> list[CheckinEvent]:
        with self._lock:
            return [
                self._by_id[i]
                for i in self._order
                if self._by_id[i].user_id == user_id and self._by_id[i].plan_id == plan_id
            ]

    def all(self) -> list[CheckinEvent]:
        """Return every event in insertion order."""
        with self._lock:
            return [self._by_id[i] for i in self._order]
