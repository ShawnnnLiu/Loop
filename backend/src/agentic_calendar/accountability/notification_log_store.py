"""Append-only notification-log store (Phase 3).

Every sponsor report generation, approval, and delivery attempt writes one
:class:`NotificationLog` here (axiom 21: "report generation, approval, and
delivery are logged"). The store is append-only: a ``notification_log_id`` may
be written exactly once. Entries are immutable audit facts, never edited.
"""

from __future__ import annotations

import threading
from typing import Protocol, runtime_checkable

from agentic_calendar.common.errors import AgenticCalendarError
from agentic_calendar.contracts.notification_log import NotificationLog


class NotificationLogStoreError(AgenticCalendarError):
    """Base for notification-log-store errors."""


class NotificationLogAlreadyExistsError(NotificationLogStoreError):
    """Attempted to append a ``notification_log_id`` that already exists."""


@runtime_checkable
class NotificationLogStore(Protocol):
    """Append/read surface for notification logs."""

    def append(self, log: NotificationLog) -> None: ...

    def list_for_report(self, report_id: str) -> list[NotificationLog]: ...

    def list_for_user(self, user_id: str) -> list[NotificationLog]: ...


class InMemoryNotificationLogStore:
    """Default Phase 3 store. Thread-safe, ephemeral, non-persistent."""

    def __init__(self) -> None:
        self._by_id: dict[str, NotificationLog] = {}
        self._order: list[str] = []
        self._lock = threading.RLock()

    def append(self, log: NotificationLog) -> None:
        """Append ``log``. Rejects a duplicate id (append-only)."""
        with self._lock:
            if log.notification_log_id in self._by_id:
                raise NotificationLogAlreadyExistsError(log.notification_log_id)
            self._by_id[log.notification_log_id] = log
            self._order.append(log.notification_log_id)

    def list_for_report(self, report_id: str) -> list[NotificationLog]:
        with self._lock:
            return [self._by_id[i] for i in self._order if self._by_id[i].report_id == report_id]

    def list_for_user(self, user_id: str) -> list[NotificationLog]:
        with self._lock:
            return [self._by_id[i] for i in self._order if self._by_id[i].user_id == user_id]
