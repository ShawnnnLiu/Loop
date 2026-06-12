"""SQLite data-access audit store (Phase 9a).

Persistent twin of
:class:`agentic_calendar.consent.audit_store.InMemoryDataAccessAuditStore`:
same :class:`~agentic_calendar.consent.audit_store.DataAccessAuditStore`
protocol, same error types, same append-only contract. Every consent-gate
check and every data-control operation writes one
:class:`DataAccessAuditEntry` here (ADR-0007: every consent-scoped access is
audited). An ``audit_entry_id`` may be written exactly once; entries are
immutable audit facts, never edited.

Deliberately **no** ``delete_for_user``: audit entries survive a user-data
deletion — the ``DATA_DELETED`` entry is the proof the deletion happened
(data-access-audit spec "Purpose").

Rows hold the canonical Pydantic JSON dump; reads rebuild the frozen model
with ``model_validate_json`` so a round trip is contract-validated, never
trusted.
"""

from __future__ import annotations

from agentic_calendar.common.sqlite import SqliteDatabase
from agentic_calendar.contracts.data_access_audit import DataAccessAuditEntry

from .audit_store import AuditEntryAlreadyExistsError

_SCHEMA_COMPONENT = "consent.data_access_audit"
_SCHEMA_VERSION = 1
_SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS data_access_audit (
        audit_entry_id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        payload TEXT NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_data_access_audit_user
        ON data_access_audit (user_id)
    """,
)


class SqliteDataAccessAuditStore:
    """Persistent audit store. Thread-safe via the shared database lock."""

    def __init__(self, db: SqliteDatabase) -> None:
        self._db = db
        db.ensure_schema(_SCHEMA_COMPONENT, version=_SCHEMA_VERSION, statements=_SCHEMA)

    def append(self, entry: DataAccessAuditEntry) -> None:
        """Append ``entry``. Rejects a duplicate id (append-only)."""
        with self._db.transaction() as cur:
            row = cur.execute(
                "SELECT 1 FROM data_access_audit WHERE audit_entry_id = ?",
                (entry.audit_entry_id,),
            ).fetchone()
            if row is not None:
                raise AuditEntryAlreadyExistsError(entry.audit_entry_id)
            cur.execute(
                "INSERT INTO data_access_audit (audit_entry_id, user_id, payload)"
                " VALUES (?, ?, ?)",
                (entry.audit_entry_id, entry.user_id, entry.model_dump_json()),
            )

    def list_for_user(self, user_id: str) -> list[DataAccessAuditEntry]:
        with self._db.read() as cur:
            rows = cur.execute(
                "SELECT payload FROM data_access_audit WHERE user_id = ?"
                " ORDER BY rowid",
                (user_id,),
            ).fetchall()
        return [DataAccessAuditEntry.model_validate_json(row[0]) for row in rows]

    def all(self) -> list[DataAccessAuditEntry]:
        """Return every entry in insertion order."""
        with self._db.read() as cur:
            rows = cur.execute(
                "SELECT payload FROM data_access_audit ORDER BY rowid"
            ).fetchall()
        return [DataAccessAuditEntry.model_validate_json(row[0]) for row in rows]
