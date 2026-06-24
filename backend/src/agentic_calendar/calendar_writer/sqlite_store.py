"""SQLite calendar-event-mapping store (Phase 9a).

Persistent twin of
:class:`agentic_calendar.calendar_writer.store.InMemoryCalendarEventMappingStore`:
same :class:`~agentic_calendar.calendar_writer.store.CalendarEventMappingStore`
protocol, same error types, same invariants. Rows hold the canonical Pydantic
JSON dump plus the key columns needed for lookups; reads rebuild the frozen
model with ``model_validate_json`` so a round trip is contract-validated,
never trusted.

Identity for a mapping is ``(run_id, task_id)``. Status transitions are
checked against the legal-transition table via
:func:`~agentic_calendar.calendar_writer.store.legal_next_states`; an illegal
transition raises and the enclosing SQL transaction's rollback preserves the
prior row — the same outcome as the in-memory store's save-prior pattern.
"""

from __future__ import annotations

from datetime import datetime

from agentic_calendar.common.sqlite import SqliteDatabase
from agentic_calendar.contracts.calendar_event_mapping import (
    CalendarEventMapping,
    CalendarWriteStatus,
)

from .store import (
    CalendarEventMappingNotFoundError,
    InvalidStatusTransitionError,
    legal_next_states,
)

_SCHEMA_COMPONENT = "calendar_writer.calendar_event_mappings"
_SCHEMA_VERSION = 1
_SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS calendar_event_mappings (
        run_id TEXT NOT NULL,
        task_id TEXT NOT NULL,
        status TEXT NOT NULL,
        payload TEXT NOT NULL,
        PRIMARY KEY (run_id, task_id)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_calendar_event_mappings_task
        ON calendar_event_mappings (task_id)
    """,
)


class SqliteCalendarEventMappingStore:
    """Persistent calendar-event-mapping store. Thread-safe via the shared
    database lock.

    Insertion order is preserved by ``list_for_run`` / ``list_for_task`` —
    rowid order matches the in-memory ``_order`` list because the upsert
    updates rows in place rather than re-inserting them.
    """

    def __init__(self, db: SqliteDatabase) -> None:
        self._db = db
        db.ensure_schema(_SCHEMA_COMPONENT, version=_SCHEMA_VERSION, statements=_SCHEMA)

    def save(self, mapping: CalendarEventMapping) -> None:
        """Insert or replace by ``(run_id, task_id)``.

        Replacement is permitted for the first save; subsequent state
        transitions must go through :meth:`update_status` to be checked
        against the legal-transition table. The upsert updates the existing
        row in place (rowid — and therefore insertion order — is preserved;
        ``INSERT OR REPLACE`` would reassign it).
        """
        with self._db.transaction() as cur:
            cur.execute(
                "INSERT INTO calendar_event_mappings (run_id, task_id, status, payload)"
                " VALUES (?, ?, ?, ?)"
                " ON CONFLICT (run_id, task_id) DO UPDATE SET"
                " status = excluded.status, payload = excluded.payload",
                (
                    mapping.run_id,
                    mapping.task_id,
                    mapping.calendar_write_status.value,
                    mapping.model_dump_json(),
                ),
            )

    def get(self, run_id: str, task_id: str) -> CalendarEventMapping:
        with self._db.read() as cur:
            row = cur.execute(
                "SELECT payload FROM calendar_event_mappings"
                " WHERE run_id = ? AND task_id = ?",
                (run_id, task_id),
            ).fetchone()
        if row is None:
            raise CalendarEventMappingNotFoundError((run_id, task_id))
        return CalendarEventMapping.model_validate_json(row[0])

    def list_for_run(self, run_id: str) -> list[CalendarEventMapping]:
        with self._db.read() as cur:
            rows = cur.execute(
                "SELECT payload FROM calendar_event_mappings WHERE run_id = ?"
                " ORDER BY rowid",
                (run_id,),
            ).fetchall()
        return [CalendarEventMapping.model_validate_json(row[0]) for row in rows]

    def list_for_task(self, task_id: str) -> list[CalendarEventMapping]:
        with self._db.read() as cur:
            rows = cur.execute(
                "SELECT payload FROM calendar_event_mappings WHERE task_id = ?"
                " ORDER BY rowid",
                (task_id,),
            ).fetchall()
        return [CalendarEventMapping.model_validate_json(row[0]) for row in rows]

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
        legal-transition table for the current status. The read-check-write
        happens inside one transaction so a concurrent transition cannot
        interleave; ``with_status`` may raise (e.g. verified-without-event-id)
        and the transaction rollback preserves the prior row, matching the
        in-memory store's assign-only-on-success behavior.
        """
        with self._db.transaction() as cur:
            row = cur.execute(
                "SELECT payload FROM calendar_event_mappings"
                " WHERE run_id = ? AND task_id = ?",
                (run_id, task_id),
            ).fetchone()
            if row is None:
                raise CalendarEventMappingNotFoundError((run_id, task_id))
            prior = CalendarEventMapping.model_validate_json(row[0])
            if new_status not in legal_next_states(prior.calendar_write_status):
                raise InvalidStatusTransitionError(
                    f"illegal calendar_write_status transition "
                    f"{prior.calendar_write_status.value!r} -> {new_status.value!r} "
                    f"for (run_id={run_id!r}, task_id={task_id!r})"
                )
            updated = prior.with_status(
                new_status, now=now, calendar_event_id=calendar_event_id
            )
            cur.execute(
                "UPDATE calendar_event_mappings SET status = ?, payload = ?"
                " WHERE run_id = ? AND task_id = ?",
                (
                    updated.calendar_write_status.value,
                    updated.model_dump_json(),
                    run_id,
                    task_id,
                ),
            )
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
        scheduled times when supplied. Not a status transition; the read-modify-
        write runs in one transaction and ``with_external_edit`` may raise (e.g.
        ``new_end <= new_start``), whereupon the rollback preserves the prior row.
        """
        with self._db.transaction() as cur:
            row = cur.execute(
                "SELECT payload FROM calendar_event_mappings"
                " WHERE run_id = ? AND task_id = ?",
                (run_id, task_id),
            ).fetchone()
            if row is None:
                raise CalendarEventMappingNotFoundError((run_id, task_id))
            prior = CalendarEventMapping.model_validate_json(row[0])
            updated = prior.with_external_edit(
                now=now, new_start=new_start, new_end=new_end
            )
            cur.execute(
                "UPDATE calendar_event_mappings SET status = ?, payload = ?"
                " WHERE run_id = ? AND task_id = ?",
                (
                    updated.calendar_write_status.value,
                    updated.model_dump_json(),
                    run_id,
                    task_id,
                ),
            )
            return updated
