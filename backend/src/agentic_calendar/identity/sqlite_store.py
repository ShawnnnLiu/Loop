"""SQLite credential store (persistent twin of ``InMemoryGoogleCredentialStore``).

Same protocol, same 1:1 sub↔user_id invariant. The row holds the canonical
Pydantic JSON dump plus the two queryable keys: ``user_id`` (primary key) and
``google_sub`` (unique). Reads rebuild the frozen model with
``model_validate_json`` so a round trip is contract-validated, never trusted.

``save`` does the conflict check and the write in one transaction: a plain
``INSERT OR REPLACE`` would silently delete a row that shares the unique
``google_sub``, so the sub is checked against the existing owner *before* the
upsert and a mismatch raises :class:`GoogleSubConflictError` (rolling back).
"""

from __future__ import annotations

from agentic_calendar.common.sqlite import SqliteDatabase

from .store import (
    GoogleCredentialRecord,
    GoogleSubConflictError,
)

_SCHEMA_COMPONENT = "identity.google_credentials"
_SCHEMA_VERSION = 1
_SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS google_credentials (
        user_id TEXT PRIMARY KEY,
        google_sub TEXT NOT NULL UNIQUE,
        payload TEXT NOT NULL
    )
    """,
)


class SqliteGoogleCredentialStore:
    """Persistent credential store. Thread-safe via the shared database lock."""

    def __init__(self, db: SqliteDatabase) -> None:
        self._db = db
        db.ensure_schema(_SCHEMA_COMPONENT, version=_SCHEMA_VERSION, statements=_SCHEMA)

    def save(self, record: GoogleCredentialRecord) -> None:
        """Upsert by ``user_id``; reject a ``google_sub`` owned by another user."""
        with self._db.transaction() as cur:
            row = cur.execute(
                "SELECT user_id FROM google_credentials WHERE google_sub = ?",
                (record.google_sub,),
            ).fetchone()
            if row is not None and row[0] != record.user_id:
                raise GoogleSubConflictError(
                    existing_user_id=row[0], attempted_user_id=record.user_id
                )
            cur.execute(
                "INSERT OR REPLACE INTO google_credentials"
                " (user_id, google_sub, payload) VALUES (?, ?, ?)",
                (record.user_id, record.google_sub, record.model_dump_json()),
            )

    def get_by_user(self, user_id: str) -> GoogleCredentialRecord | None:
        with self._db.read() as cur:
            row = cur.execute(
                "SELECT payload FROM google_credentials WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        return GoogleCredentialRecord.model_validate_json(row[0]) if row else None

    def get_user_id_for_sub(self, google_sub: str) -> str | None:
        with self._db.read() as cur:
            row = cur.execute(
                "SELECT user_id FROM google_credentials WHERE google_sub = ?",
                (google_sub,),
            ).fetchone()
        return str(row[0]) if row else None

    def delete_for_user(self, user_id: str) -> int:
        """Remove this user's credential; return the count removed (0 or 1)."""
        with self._db.transaction() as cur:
            cur.execute(
                "DELETE FROM google_credentials WHERE user_id = ?",
                (user_id,),
            )
            return cur.rowcount
