"""SQLite recommitment store (Phase 9a).

Persistent twin of
:class:`agentic_calendar.accountability.recommitment.InMemoryRecommitmentStore`:
same :class:`~agentic_calendar.accountability.recommitment.RecommitmentStore`
protocol, same error types, same append-only audit trail. Rows hold the
canonical Pydantic JSON dump; reads rebuild the frozen models with
``model_validate_json`` so a round trip is contract-validated, never trusted.

Answer-once enforcement is structural: the events table is keyed by
``recommitment_request_id`` because a request may be answered at most once —
a changed mind is a new request, so the audit trail stays append-only (spec
``docs/specs/recommitment-event.schema.md``).
"""

from __future__ import annotations

from agentic_calendar.common.sqlite import SqliteDatabase
from agentic_calendar.contracts.recommitment import (
    RecommitmentEvent,
    RecommitmentRequest,
)

from .recommitment import (
    RecommitmentAlreadyAnsweredError,
    RecommitmentRequestAlreadyExistsError,
    RecommitmentRequestNotFoundError,
)

_SCHEMA_COMPONENT = "accountability.recommitments"
_SCHEMA_VERSION = 1
_SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS recommitment_requests (
        recommitment_request_id TEXT PRIMARY KEY,
        payload TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS recommitment_events (
        recommitment_request_id TEXT PRIMARY KEY,
        payload TEXT NOT NULL
    )
    """,
)


class SqliteRecommitmentStore:
    """Persistent recommitment store. Thread-safe via the shared database lock."""

    def __init__(self, db: SqliteDatabase) -> None:
        self._db = db
        db.ensure_schema(_SCHEMA_COMPONENT, version=_SCHEMA_VERSION, statements=_SCHEMA)

    def append_request(self, request: RecommitmentRequest) -> None:
        """Insert a new request. Rejects an existing ``recommitment_request_id``."""
        with self._db.transaction() as cur:
            row = cur.execute(
                "SELECT 1 FROM recommitment_requests WHERE recommitment_request_id = ?",
                (request.recommitment_request_id,),
            ).fetchone()
            if row is not None:
                raise RecommitmentRequestAlreadyExistsError(request.recommitment_request_id)
            cur.execute(
                "INSERT INTO recommitment_requests (recommitment_request_id, payload)"
                " VALUES (?, ?)",
                (request.recommitment_request_id, request.model_dump_json()),
            )

    def append_event(self, event: RecommitmentEvent) -> None:
        """Append the answer for a known, not-yet-answered request.

        Both checks run inside the one transaction so the answer-once
        invariant holds under concurrency: an event must reference a stored
        request, and a request may be answered at most once.
        """
        with self._db.transaction() as cur:
            request_row = cur.execute(
                "SELECT 1 FROM recommitment_requests WHERE recommitment_request_id = ?",
                (event.recommitment_request_id,),
            ).fetchone()
            if request_row is None:
                raise RecommitmentRequestNotFoundError(event.recommitment_request_id)
            answered = cur.execute(
                "SELECT 1 FROM recommitment_events WHERE recommitment_request_id = ?",
                (event.recommitment_request_id,),
            ).fetchone()
            if answered is not None:
                raise RecommitmentAlreadyAnsweredError(event.recommitment_request_id)
            cur.execute(
                "INSERT INTO recommitment_events (recommitment_request_id, payload)"
                " VALUES (?, ?)",
                (event.recommitment_request_id, event.model_dump_json()),
            )

    def get_request(self, recommitment_request_id: str) -> RecommitmentRequest | None:
        with self._db.read() as cur:
            row = cur.execute(
                "SELECT payload FROM recommitment_requests"
                " WHERE recommitment_request_id = ?",
                (recommitment_request_id,),
            ).fetchone()
        return RecommitmentRequest.model_validate_json(row[0]) if row else None

    def event_for_request(self, recommitment_request_id: str) -> RecommitmentEvent | None:
        with self._db.read() as cur:
            row = cur.execute(
                "SELECT payload FROM recommitment_events"
                " WHERE recommitment_request_id = ?",
                (recommitment_request_id,),
            ).fetchone()
        return RecommitmentEvent.model_validate_json(row[0]) if row else None

    def all_requests(self) -> list[RecommitmentRequest]:
        with self._db.read() as cur:
            rows = cur.execute(
                "SELECT payload FROM recommitment_requests ORDER BY rowid"
            ).fetchall()
        return [RecommitmentRequest.model_validate_json(row[0]) for row in rows]

    def all_events(self) -> list[RecommitmentEvent]:
        with self._db.read() as cur:
            rows = cur.execute(
                "SELECT payload FROM recommitment_events ORDER BY rowid"
            ).fetchall()
        return [RecommitmentEvent.model_validate_json(row[0]) for row in rows]
