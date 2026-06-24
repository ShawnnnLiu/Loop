"""In-memory calendar-event-mapping store (Phase 2).

Identity for a mapping is ``(run_id, task_id)``. The store enforces the
status-transition table documented in
``docs/specs/calendar-event-mapping.schema.md``; any illegal transition raises
:class:`InvalidStatusTransitionError` and rolls the bucket back to its prior
value (the save-prior pattern from
:class:`agentic_calendar.planning.store.InMemoryPlanVersionStore`).

Automatic re-writes from ``verification_failed`` to ``written`` are forbidden
in production (axiom 06 lines 226-232). The store permits the transition only
because the user-triggered ``reconcile_after_crash`` path must be able to take
it; callers must not auto-retry on their own.
"""

from __future__ import annotations

import threading
from collections.abc import Iterable
from datetime import datetime
from typing import Protocol, runtime_checkable

from agentic_calendar.common.errors import AgenticCalendarError
from agentic_calendar.contracts.calendar_event_mapping import (
    CalendarEventMapping,
    CalendarWriteStatus,
)


class CalendarEventMappingStoreError(AgenticCalendarError):
    """Base for calendar-mapping-store errors."""


class CalendarEventMappingNotFoundError(CalendarEventMappingStoreError):
    pass


class InvalidStatusTransitionError(CalendarEventMappingStoreError):
    """Raised when a ``calendar_write_status`` change is not in the allowed table."""


_LEGAL_TRANSITIONS: dict[CalendarWriteStatus, frozenset[CalendarWriteStatus]] = {
    CalendarWriteStatus.DRY_RUN: frozenset(
        {CalendarWriteStatus.WRITTEN, CalendarWriteStatus.ROLLED_BACK}
    ),
    CalendarWriteStatus.WRITTEN: frozenset(
        {
            CalendarWriteStatus.VERIFIED,
            CalendarWriteStatus.VERIFICATION_FAILED,
            CalendarWriteStatus.ROLLBACK_PENDING,
        }
    ),
    CalendarWriteStatus.VERIFICATION_FAILED: frozenset(
        {CalendarWriteStatus.ROLLBACK_PENDING, CalendarWriteStatus.WRITTEN}
    ),
    CalendarWriteStatus.ROLLBACK_PENDING: frozenset(
        {CalendarWriteStatus.ROLLED_BACK, CalendarWriteStatus.ROLLBACK_FAILED}
    ),
    # VERIFIED is the only "success" state but must be reachable for rollback;
    # axiom 06 lines 132-137 require every automated write to have a rollback
    # path, and the only escape from VERIFIED is into ROLLBACK_PENDING.
    CalendarWriteStatus.VERIFIED: frozenset({CalendarWriteStatus.ROLLBACK_PENDING}),
    CalendarWriteStatus.ROLLED_BACK: frozenset(),
    CalendarWriteStatus.ROLLBACK_FAILED: frozenset(),
}


def _is_legal_transition(
    from_status: CalendarWriteStatus, to_status: CalendarWriteStatus
) -> bool:
    return to_status in _LEGAL_TRANSITIONS.get(from_status, frozenset())


@runtime_checkable
class CalendarEventMappingStore(Protocol):
    """Read/write surface for calendar event mappings."""

    def save(self, mapping: CalendarEventMapping) -> None: ...

    def get(self, run_id: str, task_id: str) -> CalendarEventMapping: ...

    def list_for_run(self, run_id: str) -> list[CalendarEventMapping]: ...

    def list_for_task(self, task_id: str) -> list[CalendarEventMapping]: ...

    def update_status(
        self,
        run_id: str,
        task_id: str,
        *,
        new_status: CalendarWriteStatus,
        now: datetime,
        calendar_event_id: str | None = None,
    ) -> CalendarEventMapping: ...

    def record_external_edit(
        self,
        run_id: str,
        task_id: str,
        *,
        now: datetime,
        new_start: datetime | None = None,
        new_end: datetime | None = None,
    ) -> CalendarEventMapping: ...


class InMemoryCalendarEventMappingStore:
    """Default Phase 2 store. Thread-safe, ephemeral, non-persistent.

    Insertion order is preserved by ``list_for_run`` / ``list_for_task`` so
    operator CLIs and tests see stable output.
    """

    def __init__(self) -> None:
        self._by_key: dict[tuple[str, str], CalendarEventMapping] = {}
        self._order: list[tuple[str, str]] = []
        self._lock = threading.RLock()

    def save(self, mapping: CalendarEventMapping) -> None:
        """Insert or replace by ``(run_id, task_id)``.

        Replacement is permitted for the first save; subsequent state
        transitions must go through :meth:`update_status` to be checked
        against the legal-transition table.
        """
        key = (mapping.run_id, mapping.task_id)
        with self._lock:
            if key not in self._by_key:
                self._order.append(key)
            self._by_key[key] = mapping

    def get(self, run_id: str, task_id: str) -> CalendarEventMapping:
        key = (run_id, task_id)
        with self._lock:
            if key not in self._by_key:
                raise CalendarEventMappingNotFoundError(key)
            return self._by_key[key]

    def list_for_run(self, run_id: str) -> list[CalendarEventMapping]:
        with self._lock:
            return [
                self._by_key[key]
                for key in self._order
                if key[0] == run_id
            ]

    def list_for_task(self, task_id: str) -> list[CalendarEventMapping]:
        with self._lock:
            return [
                self._by_key[key]
                for key in self._order
                if key[1] == task_id
            ]

    def update_status(
        self,
        run_id: str,
        task_id: str,
        *,
        new_status: CalendarWriteStatus,
        now: datetime,
        calendar_event_id: str | None = None,
    ) -> CalendarEventMapping:
        """Transition the mapping's status; rolls back on illegal transition.

        Returns the updated mapping. Raises
        :class:`InvalidStatusTransitionError` if ``new_status`` is not in the
        legal-transition table for the current status.
        """
        key = (run_id, task_id)
        with self._lock:
            if key not in self._by_key:
                raise CalendarEventMappingNotFoundError(key)
            prior = self._by_key[key]
            if not _is_legal_transition(prior.calendar_write_status, new_status):
                raise InvalidStatusTransitionError(
                    f"illegal calendar_write_status transition "
                    f"{prior.calendar_write_status.value!r} -> {new_status.value!r} "
                    f"for (run_id={run_id!r}, task_id={task_id!r})"
                )
            # ``with_status`` may raise (e.g. verified-without-event-id);
            # we let it propagate. The bucket assignment below only runs on
            # success, so the prior value is preserved on failure.
            updated = prior.with_status(
                new_status, now=now, calendar_event_id=calendar_event_id
            )
            self._by_key[key] = updated
            return updated

    def record_external_edit(
        self,
        run_id: str,
        task_id: str,
        *,
        now: datetime,
        new_start: datetime | None = None,
        new_end: datetime | None = None,
    ) -> CalendarEventMapping:
        """Record a user's direct external-calendar edit (inbound reconciliation).

        Sets ``user_modified_bool``, stamps ``last_verified_at``, and adopts new
        scheduled times when supplied. This is not a status transition, so the
        legal-transition table does not apply; the rebuild in
        ``with_external_edit`` may still raise (e.g. ``new_end <= new_start``)
        and the bucket is preserved on failure (assign only on success).
        """
        key = (run_id, task_id)
        with self._lock:
            if key not in self._by_key:
                raise CalendarEventMappingNotFoundError(key)
            prior = self._by_key[key]
            updated = prior.with_external_edit(
                now=now, new_start=new_start, new_end=new_end
            )
            self._by_key[key] = updated
            return updated


def legal_next_states(
    from_status: CalendarWriteStatus,
) -> Iterable[CalendarWriteStatus]:
    """Public read-only view of the legal-transition table (for tooling/docs)."""
    return _LEGAL_TRANSITIONS.get(from_status, frozenset())
