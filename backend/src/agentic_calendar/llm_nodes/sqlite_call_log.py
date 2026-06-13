"""SQLite llm-call-log store (Phase 9a).

Persistent twin of
:class:`agentic_calendar.llm_nodes.call_log.InMemoryLlmCallLogStore`: same
:class:`~agentic_calendar.llm_nodes.call_log.LlmCallLogStore` protocol, same
error types, same invariants. Rows hold the canonical Pydantic JSON dump plus
the ``run_id`` column needed for lookups; reads rebuild the frozen model with
``model_validate_json`` so a round trip is contract-validated, never trusted.

Like the contract and the in-memory store, this lives in ``llm_nodes/`` (the
owning region, ``docs/specs/llm-call-log.schema.md``) so the import-linter
independence set keeps observability records structurally unavailable to
runtime routing (axiom 22). The payload carries identifiers, counts, and
hashes only — never raw prompts or responses; the contract enforces that
before a row is ever written.

The append-only invariant is enforced the same way the in-memory store does it
— an existing ``llm_call_log_id`` always rejects the append. The existence
check is an explicit SELECT inside the insert transaction so a concurrent
append of the same id cannot slip past it, and so the store error stays the
typed :class:`LlmCallLogAlreadyExistsError`, never a leaked
``sqlite3.IntegrityError``.
"""

from __future__ import annotations

from agentic_calendar.common.sqlite import SqliteDatabase

from .call_log import LlmCallLog, LlmCallLogAlreadyExistsError

_SCHEMA_COMPONENT = "llm_nodes.llm_call_logs"
_SCHEMA_VERSION = 1
_SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS llm_call_logs (
        llm_call_log_id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL,
        payload TEXT NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_llm_call_logs_run
        ON llm_call_logs (run_id)
    """,
)


class SqliteLlmCallLogStore:
    """Persistent llm-call-log store. Thread-safe via the shared database lock."""

    def __init__(self, db: SqliteDatabase) -> None:
        self._db = db
        db.ensure_schema(_SCHEMA_COMPONENT, version=_SCHEMA_VERSION, statements=_SCHEMA)

    def append(self, log: LlmCallLog) -> None:
        """Append ``log``. Rejects a duplicate id (append-only)."""
        with self._db.transaction() as cur:
            row = cur.execute(
                "SELECT 1 FROM llm_call_logs WHERE llm_call_log_id = ?",
                (log.llm_call_log_id,),
            ).fetchone()
            if row is not None:
                raise LlmCallLogAlreadyExistsError(log.llm_call_log_id)
            cur.execute(
                "INSERT INTO llm_call_logs (llm_call_log_id, run_id, payload)"
                " VALUES (?, ?, ?)",
                (log.llm_call_log_id, log.run_id, log.model_dump_json()),
            )

    def list_for_run(self, run_id: str) -> list[LlmCallLog]:
        # Insertion order (rowid) — the same ordering contract as the
        # in-memory store's append list.
        with self._db.read() as cur:
            rows = cur.execute(
                "SELECT payload FROM llm_call_logs WHERE run_id = ?"
                " ORDER BY rowid",
                (run_id,),
            ).fetchall()
        return [LlmCallLog.model_validate_json(row[0]) for row in rows]

    def list_all(self) -> list[LlmCallLog]:
        with self._db.read() as cur:
            rows = cur.execute(
                "SELECT payload FROM llm_call_logs ORDER BY rowid"
            ).fetchall()
        return [LlmCallLog.model_validate_json(row[0]) for row in rows]
