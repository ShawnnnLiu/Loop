"""Append-only data-access audit store (Phase 6a).

Every consent-gate check and every data-control operation writes one
:class:`DataAccessAuditEntry` here (ADR-0007: every consent-scoped access is
audited). The store is append-only: an ``audit_entry_id`` may be written
exactly once. Entries are immutable audit facts, never edited.

Deliberately **no** ``delete_for_user``: audit entries survive a user-data
deletion — the ``DATA_DELETED`` entry is the proof the deletion happened
(data-access-audit spec "Purpose").
"""

from __future__ import annotations

import threading
from typing import Protocol, runtime_checkable

from agentic_calendar.common.errors import AgenticCalendarError
from agentic_calendar.contracts.data_access_audit import DataAccessAuditEntry


class DataAccessAuditStoreError(AgenticCalendarError):
    """Base for data-access-audit-store errors."""


class AuditEntryAlreadyExistsError(DataAccessAuditStoreError):
    """Attempted to append an ``audit_entry_id`` that already exists."""


@runtime_checkable
class DataAccessAuditStore(Protocol):
    """Append/read surface for data-access audit entries."""

    def append(self, entry: DataAccessAuditEntry) -> None: ...

    def list_for_user(self, user_id: str) -> list[DataAccessAuditEntry]: ...

    def all(self) -> list[DataAccessAuditEntry]: ...


class InMemoryDataAccessAuditStore:
    """Default Phase 6a store. Thread-safe, ephemeral, non-persistent."""

    def __init__(self) -> None:
        self._by_id: dict[str, DataAccessAuditEntry] = {}
        self._order: list[str] = []
        self._lock = threading.RLock()

    def append(self, entry: DataAccessAuditEntry) -> None:
        """Append ``entry``. Rejects a duplicate id (append-only)."""
        with self._lock:
            if entry.audit_entry_id in self._by_id:
                raise AuditEntryAlreadyExistsError(entry.audit_entry_id)
            self._by_id[entry.audit_entry_id] = entry
            self._order.append(entry.audit_entry_id)

    def list_for_user(self, user_id: str) -> list[DataAccessAuditEntry]:
        with self._lock:
            return [self._by_id[i] for i in self._order if self._by_id[i].user_id == user_id]

    def all(self) -> list[DataAccessAuditEntry]:
        """Return every entry in insertion order."""
        with self._lock:
            return [self._by_id[i] for i in self._order]
