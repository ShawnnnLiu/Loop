"""SQLite nudge audit store (Phase 9a).

Persistent twin of
:class:`agentic_calendar.accountability.nudge_store.InMemoryNudgeStore`: same
:class:`~agentic_calendar.accountability.nudge_store.NudgeStore` protocol,
same error types, same append-only invariant (axiom 21: every triggered
intervention is logged). Rows hold the canonical Pydantic JSON dump plus the
key columns needed for lookups; reads rebuild the frozen model with
``model_validate_json`` so a round trip is contract-validated, never trusted.

Append-only is enforced inside the write transaction: a duplicate ``nudge_id``
is detected by a SELECT before the INSERT and raises, exactly like the
in-memory store's dict-membership check under its lock.
"""

from __future__ import annotations

from agentic_calendar.common.sqlite import SqliteDatabase
from agentic_calendar.contracts.nudge import NudgeRecord

from .nudge_store import NudgeAlreadyExistsError

_SCHEMA_COMPONENT = "accountability.nudges"
_SCHEMA_VERSION = 1
_SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS nudges (
        nudge_id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        payload TEXT NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_nudges_user
        ON nudges (user_id)
    """,
)


class SqliteNudgeStore:
    """Persistent nudge audit store. Thread-safe via the shared database lock."""

    def __init__(self, db: SqliteDatabase) -> None:
        self._db = db
        db.ensure_schema(_SCHEMA_COMPONENT, version=_SCHEMA_VERSION, statements=_SCHEMA)

    def append(self, record: NudgeRecord) -> None:
        """Append ``record``. Rejects a duplicate id (append-only)."""
        with self._db.transaction() as cur:
            row = cur.execute(
                "SELECT 1 FROM nudges WHERE nudge_id = ?",
                (record.nudge_id,),
            ).fetchone()
            if row is not None:
                raise NudgeAlreadyExistsError(record.nudge_id)
            cur.execute(
                "INSERT INTO nudges (nudge_id, user_id, payload) VALUES (?, ?, ?)",
                (record.nudge_id, record.user_id, record.model_dump_json()),
            )

    def get(self, nudge_id: str) -> NudgeRecord | None:
        with self._db.read() as cur:
            row = cur.execute(
                "SELECT payload FROM nudges WHERE nudge_id = ?",
                (nudge_id,),
            ).fetchone()
        return NudgeRecord.model_validate_json(row[0]) if row is not None else None

    def list_for_user(self, user_id: str) -> list[NudgeRecord]:
        # Insertion order (rowid) — the same ordering contract as the
        # in-memory store's ``_order`` list.
        with self._db.read() as cur:
            rows = cur.execute(
                "SELECT payload FROM nudges WHERE user_id = ? ORDER BY rowid",
                (user_id,),
            ).fetchall()
        return [NudgeRecord.model_validate_json(row[0]) for row in rows]

    def all(self) -> list[NudgeRecord]:
        with self._db.read() as cur:
            rows = cur.execute("SELECT payload FROM nudges ORDER BY rowid").fetchall()
        return [NudgeRecord.model_validate_json(row[0]) for row in rows]
