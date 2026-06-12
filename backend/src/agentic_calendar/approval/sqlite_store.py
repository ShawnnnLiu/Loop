"""SQLite approval-event store (Phase 9a).

Persistent twin of :class:`agentic_calendar.approval.store.InMemoryApprovalEventStore`:
same :class:`~agentic_calendar.approval.store.ApprovalEventStore` protocol, same
error types, same invariants. Rows hold the canonical Pydantic JSON dump plus
the key columns needed for lookups; reads rebuild the frozen model with
``model_validate_json`` so a round trip is contract-validated, never trusted.

Approval immutability (``docs/specs/approval-event.schema.md`` line 95) is
enforced the same way the in-memory store does it — an existing
``approval_event_id`` always rejects the save, even if the payload is
byte-identical. The existence check runs inside the insert transaction so a
concurrent save of the same id cannot slip past it.
"""

from __future__ import annotations

from agentic_calendar.common.sqlite import SqliteDatabase
from agentic_calendar.contracts.approval_event import ApprovalEvent

from .store import ApprovalEventAlreadyExistsError, ApprovalEventNotFoundError

_SCHEMA_COMPONENT = "approval.approval_events"
_SCHEMA_VERSION = 1
_SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS approval_events (
        approval_event_id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        draft_schedule_id TEXT NOT NULL,
        payload TEXT NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_approval_events_user
        ON approval_events (user_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_approval_events_draft
        ON approval_events (draft_schedule_id)
    """,
)


class SqliteApprovalEventStore:
    """Persistent approval-event store. Thread-safe via the shared database lock."""

    def __init__(self, db: SqliteDatabase) -> None:
        self._db = db
        db.ensure_schema(_SCHEMA_COMPONENT, version=_SCHEMA_VERSION, statements=_SCHEMA)

    def save(self, event: ApprovalEvent) -> None:
        """Insert ``event``. Rejects any existing id (immutability).

        The duplicate check is an explicit SELECT in the same transaction —
        the store error must be the typed
        :class:`ApprovalEventAlreadyExistsError`, never a leaked
        ``sqlite3.IntegrityError``.
        """
        with self._db.transaction() as cur:
            row = cur.execute(
                "SELECT 1 FROM approval_events WHERE approval_event_id = ?",
                (event.approval_event_id,),
            ).fetchone()
            if row is not None:
                raise ApprovalEventAlreadyExistsError(event.approval_event_id)
            cur.execute(
                "INSERT INTO approval_events"
                " (approval_event_id, user_id, draft_schedule_id, payload)"
                " VALUES (?, ?, ?, ?)",
                (
                    event.approval_event_id,
                    event.user_id,
                    event.draft_schedule_id,
                    event.model_dump_json(),
                ),
            )

    def get(self, approval_event_id: str) -> ApprovalEvent:
        with self._db.read() as cur:
            row = cur.execute(
                "SELECT payload FROM approval_events WHERE approval_event_id = ?",
                (approval_event_id,),
            ).fetchone()
        if row is None:
            raise ApprovalEventNotFoundError(approval_event_id)
        return ApprovalEvent.model_validate_json(row[0])

    def list_for_user(self, user_id: str) -> list[ApprovalEvent]:
        with self._db.read() as cur:
            rows = cur.execute(
                "SELECT payload FROM approval_events WHERE user_id = ?"
                " ORDER BY rowid",
                (user_id,),
            ).fetchall()
        # Same ordering contract as the in-memory store: created_at, with
        # insertion order (rowid) as the stable tie-break.
        return sorted(
            (ApprovalEvent.model_validate_json(row[0]) for row in rows),
            key=lambda ev: ev.created_at,
        )

    def list_for_draft(self, draft_schedule_id: str) -> list[ApprovalEvent]:
        with self._db.read() as cur:
            rows = cur.execute(
                "SELECT payload FROM approval_events WHERE draft_schedule_id = ?"
                " ORDER BY rowid",
                (draft_schedule_id,),
            ).fetchall()
        # Same ordering contract as the in-memory store: created_at, with
        # insertion order (rowid) as the stable tie-break.
        return sorted(
            (ApprovalEvent.model_validate_json(row[0]) for row in rows),
            key=lambda ev: ev.created_at,
        )
