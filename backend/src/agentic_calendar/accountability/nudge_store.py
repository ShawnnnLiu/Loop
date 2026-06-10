"""Append-only nudge audit store (Phase 7).

Every private-nudge delivery attempt — sent, deferred, or dry-run — is one
immutable :class:`NudgeRecord` (axiom 21: every triggered intervention is
logged). Mirrors the notification-log store's protocol/in-memory split.
"""

from __future__ import annotations

import threading
from typing import Protocol, runtime_checkable

from agentic_calendar.common.errors import AgenticCalendarError
from agentic_calendar.contracts.nudge import NudgeRecord


class NudgeStoreError(AgenticCalendarError):
    """Base for nudge-store errors."""


class NudgeAlreadyExistsError(NudgeStoreError):
    """Attempted to append a ``nudge_id`` that already exists."""


@runtime_checkable
class NudgeStore(Protocol):
    """Append/read surface for nudge audit records."""

    def append(self, record: NudgeRecord) -> None: ...

    def get(self, nudge_id: str) -> NudgeRecord | None: ...

    def list_for_user(self, user_id: str) -> list[NudgeRecord]: ...

    def all(self) -> list[NudgeRecord]: ...


class InMemoryNudgeStore:
    """Default Phase 7 store. Thread-safe, ephemeral, non-persistent."""

    def __init__(self) -> None:
        self._by_id: dict[str, NudgeRecord] = {}
        self._order: list[str] = []
        self._lock = threading.RLock()

    def append(self, record: NudgeRecord) -> None:
        with self._lock:
            if record.nudge_id in self._by_id:
                raise NudgeAlreadyExistsError(record.nudge_id)
            self._by_id[record.nudge_id] = record
            self._order.append(record.nudge_id)

    def get(self, nudge_id: str) -> NudgeRecord | None:
        with self._lock:
            return self._by_id.get(nudge_id)

    def list_for_user(self, user_id: str) -> list[NudgeRecord]:
        with self._lock:
            return [self._by_id[i] for i in self._order if self._by_id[i].user_id == user_id]

    def all(self) -> list[NudgeRecord]:
        with self._lock:
            return [self._by_id[i] for i in self._order]
