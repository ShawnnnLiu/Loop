"""SQLite source-claim store (Phase 9a).

Persistent twin of
:class:`agentic_calendar.source_claims.ingestion.InMemorySourceClaimStore`:
same :class:`~agentic_calendar.source_claims.ingestion.SourceClaimStore`
protocol, same error types, same invariants. Rows hold the canonical Pydantic
JSON dump; reads rebuild the frozen model with ``model_validate_json`` so a
round trip is contract-validated, never trusted.

Claims are append-only with dedup by ``claim_id`` — the ingestor (the only
sanctioned producer of a claim's confidence fields, axiom 08) checks first,
and this store rejects a duplicate that slips past. The existence check is an
explicit SELECT inside the insert transaction so a concurrent append of the
same id cannot slip past it, and so the store error stays the typed
:class:`SourceClaimAlreadyExistsError`, never a leaked
``sqlite3.IntegrityError``.
"""

from __future__ import annotations

from agentic_calendar.common.sqlite import SqliteDatabase
from agentic_calendar.contracts.source_claim import SourceClaim

from .ingestion import SourceClaimAlreadyExistsError

_SCHEMA_COMPONENT = "source_claims.source_claims"
_SCHEMA_VERSION = 1
_SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS source_claims (
        claim_id TEXT PRIMARY KEY,
        payload TEXT NOT NULL
    )
    """,
)


class SqliteSourceClaimStore:
    """Persistent source-claim store. Thread-safe via the shared database lock."""

    def __init__(self, db: SqliteDatabase) -> None:
        self._db = db
        db.ensure_schema(_SCHEMA_COMPONENT, version=_SCHEMA_VERSION, statements=_SCHEMA)

    def append(self, claim: SourceClaim) -> None:
        """Append ``claim``. Rejects a duplicate id (the ingestor dedups first)."""
        with self._db.transaction() as cur:
            row = cur.execute(
                "SELECT 1 FROM source_claims WHERE claim_id = ?",
                (claim.claim_id,),
            ).fetchone()
            if row is not None:
                raise SourceClaimAlreadyExistsError(claim.claim_id)
            cur.execute(
                "INSERT INTO source_claims (claim_id, payload) VALUES (?, ?)",
                (claim.claim_id, claim.model_dump_json()),
            )

    def exists(self, claim_id: str) -> bool:
        with self._db.read() as cur:
            row = cur.execute(
                "SELECT 1 FROM source_claims WHERE claim_id = ?",
                (claim_id,),
            ).fetchone()
        return row is not None

    def get(self, claim_id: str) -> SourceClaim | None:
        with self._db.read() as cur:
            row = cur.execute(
                "SELECT payload FROM source_claims WHERE claim_id = ?",
                (claim_id,),
            ).fetchone()
        if row is None:
            return None
        return SourceClaim.model_validate_json(row[0])

    def all(self) -> list[SourceClaim]:
        # Insertion order (rowid) — the same ordering contract as the
        # in-memory store's append list.
        with self._db.read() as cur:
            rows = cur.execute(
                "SELECT payload FROM source_claims ORDER BY rowid"
            ).fetchall()
        return [SourceClaim.model_validate_json(row[0]) for row in rows]
