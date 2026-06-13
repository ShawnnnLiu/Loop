"""SQLite notification-log store (Phase 9a).

Persistent twin of
:class:`agentic_calendar.accountability.notification_log_store.InMemoryNotificationLogStore`:
same
:class:`~agentic_calendar.accountability.notification_log_store.NotificationLogStore`
protocol, same error types, same append-only invariant (axiom 21: "report
generation, approval, and delivery are logged"). Entries are immutable audit
facts, never edited. Rows hold the canonical Pydantic JSON dump plus the key
columns needed for lookups; reads rebuild the frozen model with
``model_validate_json`` so a round trip is contract-validated, never trusted.

Append-only is enforced inside the write transaction: a duplicate
``notification_log_id`` is detected by a SELECT before the INSERT and raises,
exactly like the in-memory store's dict-membership check under its lock.
"""

from __future__ import annotations

from agentic_calendar.common.sqlite import SqliteDatabase
from agentic_calendar.contracts.notification_log import NotificationLog

from .notification_log_store import NotificationLogAlreadyExistsError

_SCHEMA_COMPONENT = "accountability.notification_logs"
_SCHEMA_VERSION = 1
_SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS notification_logs (
        notification_log_id TEXT PRIMARY KEY,
        report_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        payload TEXT NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_notification_logs_report
        ON notification_logs (report_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_notification_logs_user
        ON notification_logs (user_id)
    """,
)


class SqliteNotificationLogStore:
    """Persistent notification-log store. Thread-safe via the shared database lock."""

    def __init__(self, db: SqliteDatabase) -> None:
        self._db = db
        db.ensure_schema(_SCHEMA_COMPONENT, version=_SCHEMA_VERSION, statements=_SCHEMA)

    def append(self, log: NotificationLog) -> None:
        """Append ``log``. Rejects a duplicate id (append-only)."""
        with self._db.transaction() as cur:
            row = cur.execute(
                "SELECT 1 FROM notification_logs WHERE notification_log_id = ?",
                (log.notification_log_id,),
            ).fetchone()
            if row is not None:
                raise NotificationLogAlreadyExistsError(log.notification_log_id)
            cur.execute(
                "INSERT INTO notification_logs"
                " (notification_log_id, report_id, user_id, payload)"
                " VALUES (?, ?, ?, ?)",
                (log.notification_log_id, log.report_id, log.user_id, log.model_dump_json()),
            )

    def list_for_report(self, report_id: str) -> list[NotificationLog]:
        # Insertion order (rowid) — the same ordering contract as the
        # in-memory store's ``_order`` list.
        with self._db.read() as cur:
            rows = cur.execute(
                "SELECT payload FROM notification_logs WHERE report_id = ? ORDER BY rowid",
                (report_id,),
            ).fetchall()
        return [NotificationLog.model_validate_json(row[0]) for row in rows]

    def list_for_user(self, user_id: str) -> list[NotificationLog]:
        with self._db.read() as cur:
            rows = cur.execute(
                "SELECT payload FROM notification_logs WHERE user_id = ? ORDER BY rowid",
                (user_id,),
            ).fetchall()
        return [NotificationLog.model_validate_json(row[0]) for row in rows]
