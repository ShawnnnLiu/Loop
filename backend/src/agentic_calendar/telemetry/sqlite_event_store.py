"""SQLite telemetry-event store (Phase 9a).

Persistent twin of
:class:`agentic_calendar.telemetry.event_store.InMemoryTelemetryEventStore`:
same :class:`~agentic_calendar.telemetry.event_store.TelemetryEventStore`
protocol, same error types, same invariants. Rows hold the canonical Pydantic
JSON dump plus the ``task_id`` column needed for lookups; reads rebuild the
frozen model with ``model_validate_json`` so a round trip is
contract-validated, never trusted.

The append-only invariant (telemetry spec: "events are append-only and never
silently mutated") is enforced the same way the in-memory store does it — an
existing ``telemetry_event_id`` always rejects the append. The existence check
is an explicit SELECT inside the insert transaction so a concurrent append of
the same id cannot slip past it, and so the store error stays the typed
:class:`TelemetryEventAlreadyExistsError`, never a leaked
``sqlite3.IntegrityError``.

:meth:`delete_for_tasks` is the explicit, audited exception to append-only
(ADR-0007 user data delete), mirroring the in-memory twin.
"""

from __future__ import annotations

from agentic_calendar.common.sqlite import SqliteDatabase
from agentic_calendar.contracts.telemetry import TelemetryEvent

from .event_store import TelemetryEventAlreadyExistsError

_SCHEMA_COMPONENT = "telemetry.telemetry_events"
_SCHEMA_VERSION = 1
_SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS telemetry_events (
        telemetry_event_id TEXT PRIMARY KEY,
        task_id TEXT NOT NULL,
        payload TEXT NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_telemetry_events_task
        ON telemetry_events (task_id)
    """,
)

#: Maximum ids per parameterized ``IN`` clause — comfortably under SQLite's
#: classic 999-variable limit, so a large delete never trips it.
_IN_CLAUSE_CHUNK = 500


class SqliteTelemetryEventStore:
    """Persistent telemetry-event store. Thread-safe via the shared database lock."""

    def __init__(self, db: SqliteDatabase) -> None:
        self._db = db
        db.ensure_schema(_SCHEMA_COMPONENT, version=_SCHEMA_VERSION, statements=_SCHEMA)

    def append(self, event: TelemetryEvent) -> None:
        """Append ``event``. Rejects a duplicate id (append-only)."""
        with self._db.transaction() as cur:
            row = cur.execute(
                "SELECT 1 FROM telemetry_events WHERE telemetry_event_id = ?",
                (event.telemetry_event_id,),
            ).fetchone()
            if row is not None:
                raise TelemetryEventAlreadyExistsError(event.telemetry_event_id)
            cur.execute(
                "INSERT INTO telemetry_events (telemetry_event_id, task_id, payload)"
                " VALUES (?, ?, ?)",
                (event.telemetry_event_id, event.task_id, event.model_dump_json()),
            )

    def exists(self, telemetry_event_id: str) -> bool:
        with self._db.read() as cur:
            row = cur.execute(
                "SELECT 1 FROM telemetry_events WHERE telemetry_event_id = ?",
                (telemetry_event_id,),
            ).fetchone()
        return row is not None

    def get(self, telemetry_event_id: str) -> TelemetryEvent | None:
        with self._db.read() as cur:
            row = cur.execute(
                "SELECT payload FROM telemetry_events WHERE telemetry_event_id = ?",
                (telemetry_event_id,),
            ).fetchone()
        if row is None:
            return None
        return TelemetryEvent.model_validate_json(row[0])

    def list_for_task(self, task_id: str) -> list[TelemetryEvent]:
        # Insertion order (rowid) — the same ordering contract as the
        # in-memory store's append list.
        with self._db.read() as cur:
            rows = cur.execute(
                "SELECT payload FROM telemetry_events WHERE task_id = ?"
                " ORDER BY rowid",
                (task_id,),
            ).fetchall()
        return [TelemetryEvent.model_validate_json(row[0]) for row in rows]

    def all(self) -> list[TelemetryEvent]:
        """Return every event in insertion order."""
        with self._db.read() as cur:
            rows = cur.execute(
                "SELECT payload FROM telemetry_events ORDER BY rowid"
            ).fetchall()
        return [TelemetryEvent.model_validate_json(row[0]) for row in rows]

    def delete_for_tasks(self, task_ids: set[str]) -> int:
        """Remove every event for ``task_ids``; return the count removed.

        The only caller is the user data-delete control (ADR-0007), which
        scopes a user's events by their task ids and writes a ``DATA_DELETED``
        audit entry. This is the explicit, audited exception to the
        append-only invariant — a user-requested erasure is not a *silent*
        mutation (telemetry spec: "never silently mutated").

        Deletes run in one transaction so a partial erasure can never be
        observed; the ``IN`` clauses are chunked so the id set can exceed
        SQLite's bound-variable limit. Ids are sorted first so the statement
        sequence is deterministic for a given set.
        """
        if not task_ids:
            return 0
        ordered = sorted(task_ids)
        removed = 0
        with self._db.transaction() as cur:
            for start in range(0, len(ordered), _IN_CLAUSE_CHUNK):
                chunk = ordered[start : start + _IN_CLAUSE_CHUNK]
                placeholders = ", ".join("?" for _ in chunk)
                cur.execute(
                    f"DELETE FROM telemetry_events WHERE task_id IN ({placeholders})",
                    chunk,
                )
                removed += cur.rowcount
        return removed
