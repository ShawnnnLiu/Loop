"""In-memory approval-event store (Phase 2).

Persistence-backed implementations land in a later phase. The Phase 2
in-memory version follows the exact concurrency / rollback shape of
:class:`agentic_calendar.planning.store.InMemoryPlanVersionStore`.

The store enforces approval immutability at the persistence boundary
(``docs/specs/approval-event.schema.md`` line 95): once an
``approval_event_id`` is saved, any attempt to re-save the same id raises
:class:`ApprovalEventAlreadyExistsError`, even if the payload is byte-identical.
The Pydantic model itself is ``frozen=True``, but the store is the ultimate
authority since multiple model instances with the same id may exist in memory.
"""

from __future__ import annotations

import threading
from typing import Protocol, runtime_checkable

from agentic_calendar.common.errors import AgenticCalendarError
from agentic_calendar.contracts.approval_event import ApprovalEvent


class ApprovalEventStoreError(AgenticCalendarError):
    """Base for approval-store errors that callers may catch."""


class ApprovalEventAlreadyExistsError(ApprovalEventStoreError):
    """Attempted to save an ``approval_event_id`` that already exists.

    Approval events are immutable; re-save is always a programming error.
    """


class ApprovalEventNotFoundError(ApprovalEventStoreError):
    pass


@runtime_checkable
class ApprovalEventStore(Protocol):
    """Read/write surface for approval events."""

    def save(self, event: ApprovalEvent) -> None: ...

    def get(self, approval_event_id: str) -> ApprovalEvent: ...

    def list_for_user(self, user_id: str) -> list[ApprovalEvent]: ...

    def list_for_draft(self, draft_schedule_id: str) -> list[ApprovalEvent]: ...


class InMemoryApprovalEventStore:
    """Default Phase 2 store. Thread-safe, ephemeral, non-persistent."""

    def __init__(self) -> None:
        self._by_id: dict[str, ApprovalEvent] = {}
        self._lock = threading.RLock()

    def save(self, event: ApprovalEvent) -> None:
        """Insert ``event``. Rejects any existing id (immutability)."""
        with self._lock:
            if event.approval_event_id in self._by_id:
                raise ApprovalEventAlreadyExistsError(event.approval_event_id)
            self._by_id[event.approval_event_id] = event

    def get(self, approval_event_id: str) -> ApprovalEvent:
        with self._lock:
            if approval_event_id not in self._by_id:
                raise ApprovalEventNotFoundError(approval_event_id)
            return self._by_id[approval_event_id]

    def list_for_user(self, user_id: str) -> list[ApprovalEvent]:
        with self._lock:
            return sorted(
                (ev for ev in self._by_id.values() if ev.user_id == user_id),
                key=lambda ev: ev.created_at,
            )

    def list_for_draft(self, draft_schedule_id: str) -> list[ApprovalEvent]:
        with self._lock:
            return sorted(
                (
                    ev
                    for ev in self._by_id.values()
                    if ev.draft_schedule_id == draft_schedule_id
                ),
                key=lambda ev: ev.created_at,
            )
