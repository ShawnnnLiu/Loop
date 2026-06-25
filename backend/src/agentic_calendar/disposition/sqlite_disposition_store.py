"""SQLite task-disposition store (restart-survival twin).

Persistent twin of
:class:`agentic_calendar.disposition.disposition_store.InMemoryTaskDispositionStore`:
same :class:`~agentic_calendar.disposition.disposition_store.TaskDispositionStore`
protocol, same error types, same append-only invariant. Rows hold the canonical
Pydantic JSON dump plus the key columns needed for lookups; reads rebuild the
frozen model with ``model_validate_json`` so a round trip is contract-validated,
never trusted.

Append-only is enforced inside the write transaction: a duplicate
``disposition_id`` is detected by a SELECT before the INSERT and raises, exactly
like the in-memory store's dict-membership check under its lock.
"""

from __future__ import annotations

from agentic_calendar.common.sqlite import SqliteDatabase
from agentic_calendar.contracts.task_disposition import (
    TaskDispositionRecord,
    TaskDispositionType,
)

from .disposition_store import TaskDispositionAlreadyExistsError

_SCHEMA_COMPONENT = "disposition.task_dispositions"
_SCHEMA_VERSION = 1
_SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS task_dispositions (
        disposition_id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        plan_version TEXT NOT NULL,
        task_id TEXT NOT NULL,
        disposition TEXT NOT NULL,
        payload TEXT NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_task_dispositions_user
        ON task_dispositions (user_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_task_dispositions_user_disposition
        ON task_dispositions (user_id, disposition)
    """,
)


class SqliteTaskDispositionStore:
    """Persistent task-disposition store. Thread-safe via the shared database lock."""

    def __init__(self, db: SqliteDatabase) -> None:
        self._db = db
        db.ensure_schema(_SCHEMA_COMPONENT, version=_SCHEMA_VERSION, statements=_SCHEMA)

    def append(self, record: TaskDispositionRecord) -> None:
        """Append ``record``. Rejects a duplicate id (append-only)."""
        with self._db.transaction() as cur:
            row = cur.execute(
                "SELECT 1 FROM task_dispositions WHERE disposition_id = ?",
                (record.disposition_id,),
            ).fetchone()
            if row is not None:
                raise TaskDispositionAlreadyExistsError(record.disposition_id)
            cur.execute(
                "INSERT INTO task_dispositions"
                " (disposition_id, user_id, plan_version, task_id, disposition, payload)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (
                    record.disposition_id,
                    record.user_id,
                    record.plan_version,
                    record.task_id,
                    record.disposition.value,
                    record.model_dump_json(),
                ),
            )

    def exists(self, disposition_id: str) -> bool:
        with self._db.read() as cur:
            row = cur.execute(
                "SELECT 1 FROM task_dispositions WHERE disposition_id = ?",
                (disposition_id,),
            ).fetchone()
        return row is not None

    def list_for_user(self, user_id: str) -> list[TaskDispositionRecord]:
        # Insertion order (rowid) — the same ordering contract as the in-memory
        # store's ``_order`` list.
        with self._db.read() as cur:
            rows = cur.execute(
                "SELECT payload FROM task_dispositions"
                " WHERE user_id = ? ORDER BY rowid",
                (user_id,),
            ).fetchall()
        return [TaskDispositionRecord.model_validate_json(row[0]) for row in rows]

    def list_for_plan(
        self, user_id: str, plan_version: str
    ) -> list[TaskDispositionRecord]:
        with self._db.read() as cur:
            rows = cur.execute(
                "SELECT payload FROM task_dispositions"
                " WHERE user_id = ? AND plan_version = ? ORDER BY rowid",
                (user_id, plan_version),
            ).fetchall()
        return [TaskDispositionRecord.model_validate_json(row[0]) for row in rows]

    def task_ids_with_disposition(
        self, user_id: str, disposition: TaskDispositionType
    ) -> set[str]:
        with self._db.read() as cur:
            rows = cur.execute(
                "SELECT DISTINCT task_id FROM task_dispositions"
                " WHERE user_id = ? AND disposition = ?",
                (user_id, disposition.value),
            ).fetchall()
        return {row[0] for row in rows}

    def delete_for_user(self, user_id: str) -> int:
        """Remove every record for ``user_id`` (ADR-0007 data-delete control)."""
        with self._db.transaction() as cur:
            cur.execute("DELETE FROM task_dispositions WHERE user_id = ?", (user_id,))
            return cur.rowcount
