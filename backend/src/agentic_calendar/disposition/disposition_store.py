"""Append-only task-disposition store (completion / drop memory).

Every completion / skip / drop is one immutable :class:`TaskDispositionRecord`.
The store is append-only: a ``disposition_id`` may be written exactly once.
Mirrors the check-in / telemetry event stores' protocol / in-memory split so the
SQLite twin can swap in for restart survival.

Two deterministic consumers read it (task-disposition spec): the scheduler
projection (``task_ids_with_disposition`` → ``SchedulerInput.completed_task_ids``)
and the completion-relative drag-to-adjust advisory check (ADR-0008).
``delete_for_user`` exists for the ADR-0007 data-delete control, exactly like the
``identity`` and ``consent`` stores.
"""

from __future__ import annotations

import threading
from typing import Protocol, runtime_checkable

from agentic_calendar.common.errors import AgenticCalendarError
from agentic_calendar.contracts.task_disposition import (
    TaskDispositionRecord,
    TaskDispositionType,
)


class TaskDispositionStoreError(AgenticCalendarError):
    """Base for task-disposition-store errors."""


class TaskDispositionAlreadyExistsError(TaskDispositionStoreError):
    """Attempted to append a ``disposition_id`` that already exists."""


@runtime_checkable
class TaskDispositionStore(Protocol):
    """Append / read / delete surface for task dispositions."""

    def append(self, record: TaskDispositionRecord) -> None: ...

    def exists(self, disposition_id: str) -> bool: ...

    def list_for_user(self, user_id: str) -> list[TaskDispositionRecord]: ...

    def list_for_plan(
        self, user_id: str, plan_version: str
    ) -> list[TaskDispositionRecord]: ...

    def task_ids_with_disposition(
        self, user_id: str, disposition: TaskDispositionType
    ) -> set[str]: ...

    def delete_for_user(self, user_id: str) -> int: ...


class InMemoryTaskDispositionStore:
    """Default store. Thread-safe, ephemeral, non-persistent."""

    def __init__(self) -> None:
        self._by_id: dict[str, TaskDispositionRecord] = {}
        self._order: list[str] = []
        self._lock = threading.RLock()

    def append(self, record: TaskDispositionRecord) -> None:
        """Append ``record``. Rejects a duplicate id (append-only)."""
        with self._lock:
            if record.disposition_id in self._by_id:
                raise TaskDispositionAlreadyExistsError(record.disposition_id)
            self._by_id[record.disposition_id] = record
            self._order.append(record.disposition_id)

    def exists(self, disposition_id: str) -> bool:
        with self._lock:
            return disposition_id in self._by_id

    def list_for_user(self, user_id: str) -> list[TaskDispositionRecord]:
        with self._lock:
            return [
                self._by_id[i] for i in self._order if self._by_id[i].user_id == user_id
            ]

    def list_for_plan(
        self, user_id: str, plan_version: str
    ) -> list[TaskDispositionRecord]:
        with self._lock:
            return [
                self._by_id[i]
                for i in self._order
                if self._by_id[i].user_id == user_id
                and self._by_id[i].plan_version == plan_version
            ]

    def task_ids_with_disposition(
        self, user_id: str, disposition: TaskDispositionType
    ) -> set[str]:
        """Task ids the user has with ``disposition`` across **all** plan
        versions; ids are stable across plan versions (task-disposition spec)."""
        with self._lock:
            return {
                self._by_id[i].task_id
                for i in self._order
                if self._by_id[i].user_id == user_id
                and self._by_id[i].disposition is disposition
            }

    def delete_for_user(self, user_id: str) -> int:
        """Remove every record for ``user_id`` (ADR-0007 data-delete control)."""
        with self._lock:
            doomed = {i for i in self._order if self._by_id[i].user_id == user_id}
            for i in doomed:
                del self._by_id[i]
            self._order = [i for i in self._order if i in self._by_id]
            return len(doomed)
