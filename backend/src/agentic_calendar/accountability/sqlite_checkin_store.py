"""SQLite check-in event store (Phase 9a).

Persistent twin of
:class:`agentic_calendar.accountability.checkin_store.InMemoryCheckinEventStore`:
same :class:`~agentic_calendar.accountability.checkin_store.CheckinEventStore`
protocol, same error types, same append-only invariant (axiom 21: "check-in
records are append-only"). Rows hold the canonical Pydantic JSON dump plus the
key columns needed for lookups; reads rebuild the frozen model with
``model_validate_json`` so a round trip is contract-validated, never trusted.

Append-only is enforced inside the write transaction: a duplicate
``checkin_id`` is detected by a SELECT before the INSERT and raises, exactly
like the in-memory store's dict-membership check under its lock.
"""

from __future__ import annotations

from agentic_calendar.common.sqlite import SqliteDatabase
from agentic_calendar.contracts.checkin_event import CheckinEvent

from .checkin_store import CheckinEventAlreadyExistsError

_SCHEMA_COMPONENT = "accountability.checkin_events"
_SCHEMA_VERSION = 1
_SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS checkin_events (
        checkin_id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        plan_id TEXT NOT NULL,
        payload TEXT NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_checkin_events_user_plan
        ON checkin_events (user_id, plan_id)
    """,
)


class SqliteCheckinEventStore:
    """Persistent check-in event store. Thread-safe via the shared database lock."""

    def __init__(self, db: SqliteDatabase) -> None:
        self._db = db
        db.ensure_schema(_SCHEMA_COMPONENT, version=_SCHEMA_VERSION, statements=_SCHEMA)

    def append(self, event: CheckinEvent) -> None:
        """Append ``event``. Rejects a duplicate id (append-only)."""
        with self._db.transaction() as cur:
            row = cur.execute(
                "SELECT 1 FROM checkin_events WHERE checkin_id = ?",
                (event.checkin_id,),
            ).fetchone()
            if row is not None:
                raise CheckinEventAlreadyExistsError(event.checkin_id)
            cur.execute(
                "INSERT INTO checkin_events (checkin_id, user_id, plan_id, payload)"
                " VALUES (?, ?, ?, ?)",
                (event.checkin_id, event.user_id, event.plan_id, event.model_dump_json()),
            )

    def exists(self, checkin_id: str) -> bool:
        with self._db.read() as cur:
            row = cur.execute(
                "SELECT 1 FROM checkin_events WHERE checkin_id = ?",
                (checkin_id,),
            ).fetchone()
        return row is not None

    def get(self, checkin_id: str) -> CheckinEvent | None:
        with self._db.read() as cur:
            row = cur.execute(
                "SELECT payload FROM checkin_events WHERE checkin_id = ?",
                (checkin_id,),
            ).fetchone()
        return CheckinEvent.model_validate_json(row[0]) if row is not None else None

    def list_for_plan(self, user_id: str, plan_id: str) -> list[CheckinEvent]:
        # Insertion order (rowid) — the same ordering contract as the
        # in-memory store's ``_order`` list.
        with self._db.read() as cur:
            rows = cur.execute(
                "SELECT payload FROM checkin_events"
                " WHERE user_id = ? AND plan_id = ? ORDER BY rowid",
                (user_id, plan_id),
            ).fetchall()
        return [CheckinEvent.model_validate_json(row[0]) for row in rows]

    def all(self) -> list[CheckinEvent]:
        """Return every event in insertion order."""
        with self._db.read() as cur:
            rows = cur.execute("SELECT payload FROM checkin_events ORDER BY rowid").fetchall()
        return [CheckinEvent.model_validate_json(row[0]) for row in rows]
