"""SQLite plan-version store (Phase 9a).

Persistent twin of :class:`agentic_calendar.planning.store.InMemoryPlanVersionStore`:
same :class:`~agentic_calendar.planning.store.PlanVersionStore` protocol, same
error types, same invariants. Rows hold the canonical Pydantic JSON dump plus
the key columns needed for lookups; reads rebuild the frozen model with
``model_validate_json`` so a round trip is contract-validated, never trusted.

The single-active invariant is enforced the same way the in-memory store does
it — write first, re-check, undo on violation — except the undo is the
enclosing SQL transaction's rollback rather than a saved prior value.
"""

from __future__ import annotations

from agentic_calendar.common.sqlite import SqliteDatabase

from .plan_version import LifecycleState, PlanVersion
from .store import MultipleActivePlansError, PlanVersionNotFoundError

_SCHEMA_COMPONENT = "planning.plan_versions"
_SCHEMA_VERSION = 1
_SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS plan_versions (
        user_id TEXT NOT NULL,
        plan_version TEXT NOT NULL,
        state TEXT NOT NULL,
        payload TEXT NOT NULL,
        PRIMARY KEY (user_id, plan_version)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_plan_versions_user_state
        ON plan_versions (user_id, state)
    """,
)


class SqlitePlanVersionStore:
    """Persistent plan-version store. Thread-safe via the shared database lock."""

    def __init__(self, db: SqliteDatabase) -> None:
        self._db = db
        db.ensure_schema(_SCHEMA_COMPONENT, version=_SCHEMA_VERSION, statements=_SCHEMA)

    def save(self, plan_version: PlanVersion) -> None:
        """Insert or replace by ``(user_id, plan_version)``.

        The upsert updates the existing row in place (rowid — and therefore
        insertion order — is preserved). The single-active invariant is
        re-checked inside the same transaction; a violation raises and the
        rollback restores the prior state, so the store stays queryable.
        """
        with self._db.transaction() as cur:
            cur.execute(
                "INSERT INTO plan_versions (user_id, plan_version, state, payload)"
                " VALUES (?, ?, ?, ?)"
                " ON CONFLICT (user_id, plan_version) DO UPDATE SET"
                " state = excluded.state, payload = excluded.payload",
                (
                    plan_version.user_id,
                    plan_version.plan_version,
                    plan_version.state.value,
                    plan_version.model_dump_json(),
                ),
            )
            row = cur.execute(
                "SELECT COUNT(*) FROM plan_versions WHERE user_id = ? AND state = ?",
                (plan_version.user_id, LifecycleState.ACTIVE.value),
            ).fetchone()
            if row[0] > 1:
                raise MultipleActivePlansError(plan_version.user_id)

    def get(self, user_id: str, plan_version: str) -> PlanVersion:
        with self._db.read() as cur:
            row = cur.execute(
                "SELECT payload FROM plan_versions"
                " WHERE user_id = ? AND plan_version = ?",
                (user_id, plan_version),
            ).fetchone()
        if row is None:
            raise PlanVersionNotFoundError(plan_version)
        return PlanVersion.model_validate_json(row[0])

    def list_for_user(self, user_id: str) -> list[PlanVersion]:
        with self._db.read() as cur:
            rows = cur.execute(
                "SELECT payload FROM plan_versions WHERE user_id = ?"
                " ORDER BY rowid",
                (user_id,),
            ).fetchall()
        # Same ordering contract as the in-memory store: created_at, with
        # insertion order (rowid) as the stable tie-break.
        return sorted(
            (PlanVersion.model_validate_json(row[0]) for row in rows),
            key=lambda pv: pv.created_at,
        )

    def get_active(self, user_id: str) -> PlanVersion | None:
        with self._db.read() as cur:
            rows = cur.execute(
                "SELECT payload FROM plan_versions WHERE user_id = ? AND state = ?"
                " ORDER BY rowid",
                (user_id, LifecycleState.ACTIVE.value),
            ).fetchall()
        if len(rows) > 1:
            raise MultipleActivePlansError(user_id)
        return PlanVersion.model_validate_json(rows[0][0]) if rows else None
