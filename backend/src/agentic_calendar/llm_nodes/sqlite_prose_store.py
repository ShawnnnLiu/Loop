"""SQLite prose-attachment store (UX pass B5).

Persistent twin of
:class:`agentic_calendar.llm_nodes.prose_attachment.InMemoryProseAttachmentStore`:
same protocol, same error types, same invariants. Rows hold the canonical
Pydantic JSON dump plus the ``run_id`` / ``user_id`` / ``kind`` columns needed
for lookups; reads rebuild the frozen model with ``model_validate_json`` so a
round trip is contract-validated, never trusted.

Placement mirrors ``sqlite_call_log.py``: the record lives in ``llm_nodes/``
(the owning region per ``docs/specs/prose-attachment.schema.md``) so the
import-linter independence set keeps prose structurally unavailable to runtime
routing — display and advisory prompt context only.
"""

from __future__ import annotations

from agentic_calendar.common.sqlite import SqliteDatabase

from .prose_attachment import (
    ProseAttachmentAlreadyExistsError,
    ProseAttachmentKind,
    ProseAttachmentRecord,
)

_SCHEMA_COMPONENT = "llm_nodes.prose_attachments"
_SCHEMA_VERSION = 1
_SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS prose_attachments (
        prose_attachment_id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        run_id TEXT NOT NULL,
        kind TEXT NOT NULL,
        payload TEXT NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_prose_attachments_run
        ON prose_attachments (run_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_prose_attachments_user
        ON prose_attachments (user_id)
    """,
)


class SqliteProseAttachmentStore:
    """Persistent prose-attachment store. Thread-safe via the shared db lock."""

    def __init__(self, db: SqliteDatabase) -> None:
        self._db = db
        db.ensure_schema(_SCHEMA_COMPONENT, version=_SCHEMA_VERSION, statements=_SCHEMA)

    def append(self, record: ProseAttachmentRecord) -> None:
        """Append ``record``. Rejects a duplicate id (append-only)."""
        with self._db.transaction() as cur:
            row = cur.execute(
                "SELECT 1 FROM prose_attachments WHERE prose_attachment_id = ?",
                (record.prose_attachment_id,),
            ).fetchone()
            if row is not None:
                raise ProseAttachmentAlreadyExistsError(record.prose_attachment_id)
            cur.execute(
                "INSERT INTO prose_attachments"
                " (prose_attachment_id, user_id, run_id, kind, payload)"
                " VALUES (?, ?, ?, ?, ?)",
                (
                    record.prose_attachment_id,
                    record.user_id,
                    record.run_id,
                    record.kind.value,
                    record.model_dump_json(),
                ),
            )

    def list_for_run(self, run_id: str) -> list[ProseAttachmentRecord]:
        with self._db.read() as cur:
            rows = cur.execute(
                "SELECT payload FROM prose_attachments WHERE run_id = ?"
                " ORDER BY rowid",
                (run_id,),
            ).fetchall()
        return [ProseAttachmentRecord.model_validate_json(row[0]) for row in rows]

    def list_for_user(self, user_id: str) -> list[ProseAttachmentRecord]:
        with self._db.read() as cur:
            rows = cur.execute(
                "SELECT payload FROM prose_attachments WHERE user_id = ?"
                " ORDER BY rowid",
                (user_id,),
            ).fetchall()
        return [ProseAttachmentRecord.model_validate_json(row[0]) for row in rows]

    def latest_for_run(
        self, run_id: str, *, kind: ProseAttachmentKind
    ) -> ProseAttachmentRecord | None:
        with self._db.read() as cur:
            row = cur.execute(
                "SELECT payload FROM prose_attachments"
                " WHERE run_id = ? AND kind = ?"
                " ORDER BY rowid DESC LIMIT 1",
                (run_id, kind.value),
            ).fetchone()
        if row is None:
            return None
        return ProseAttachmentRecord.model_validate_json(row[0])

    def delete_for_user(self, user_id: str) -> int:
        """Erase a user's derived prose (they are personal data — spec rule)."""
        with self._db.transaction() as cur:
            cur.execute(
                "DELETE FROM prose_attachments WHERE user_id = ?", (user_id,)
            )
            return cur.rowcount
