"""SQLite sponsor store (Phase 9a).

Persistent twin of
:class:`agentic_calendar.accountability.sponsor_store.InMemorySponsorStore`:
same :class:`~agentic_calendar.accountability.sponsor_store.SponsorStore`
protocol, same error types, same lifecycle authority. Rows hold the canonical
Pydantic JSON dump plus the key columns needed for lookups; reads rebuild the
frozen :class:`Sponsor` with ``model_validate_json`` so a round trip is
contract-validated, never trusted.

The store remains the authority for transition legality — it rejects any
transition not permitted by ``ALLOWED_SPONSOR_TRANSITIONS`` so that no caller
can reactivate a revoked sponsor or skip acceptance (spec "Invite Lifecycle").
Each transition writes a new frozen :class:`Sponsor` row; nothing mutates in
place.
"""

from __future__ import annotations

from agentic_calendar.common.clock import Clock
from agentic_calendar.common.sqlite import SqliteDatabase
from agentic_calendar.contracts.sponsor import (
    Sponsor,
    SponsorStatus,
    is_allowed_sponsor_transition,
)

from .sponsor_store import (
    IllegalSponsorTransitionError,
    SponsorAlreadyExistsError,
    SponsorNotFoundError,
)

_SCHEMA_COMPONENT = "accountability.sponsors"
_SCHEMA_VERSION = 1
_SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS sponsors (
        sponsor_id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        status TEXT NOT NULL,
        payload TEXT NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_sponsors_user
        ON sponsors (user_id)
    """,
)


class SqliteSponsorStore:
    """Persistent sponsor store. Thread-safe via the shared database lock."""

    def __init__(self, db: SqliteDatabase, clock: Clock) -> None:
        self._db = db
        self._clock = clock
        db.ensure_schema(_SCHEMA_COMPONENT, version=_SCHEMA_VERSION, statements=_SCHEMA)

    def invite(self, sponsor: Sponsor) -> None:
        """Insert a new sponsor row. Rejects an existing ``sponsor_id``."""
        with self._db.transaction() as cur:
            row = cur.execute(
                "SELECT 1 FROM sponsors WHERE sponsor_id = ?",
                (sponsor.sponsor_id,),
            ).fetchone()
            if row is not None:
                raise SponsorAlreadyExistsError(sponsor.sponsor_id)
            cur.execute(
                "INSERT INTO sponsors (sponsor_id, user_id, status, payload)"
                " VALUES (?, ?, ?, ?)",
                (
                    sponsor.sponsor_id,
                    sponsor.user_id,
                    sponsor.status.value,
                    sponsor.model_dump_json(),
                ),
            )

    def get(self, sponsor_id: str) -> Sponsor:
        with self._db.read() as cur:
            row = cur.execute(
                "SELECT payload FROM sponsors WHERE sponsor_id = ?",
                (sponsor_id,),
            ).fetchone()
        if row is None:
            raise SponsorNotFoundError(sponsor_id)
        return Sponsor.model_validate_json(row[0])

    def accept(self, sponsor_id: str) -> Sponsor:
        """Transition ``pending → accepted`` and stamp ``accepted_at``."""
        return self._transition(sponsor_id, SponsorStatus.ACCEPTED)

    def revoke(self, sponsor_id: str) -> Sponsor:
        """Transition ``pending|accepted → revoked`` and stamp ``revoked_at``.

        Revocation takes effect immediately so the next generated report sees
        the new status (spec "Invite Lifecycle")."""
        return self._transition(sponsor_id, SponsorStatus.REVOKED)

    def list_for_user(self, user_id: str) -> list[Sponsor]:
        with self._db.read() as cur:
            rows = cur.execute(
                "SELECT payload FROM sponsors WHERE user_id = ? ORDER BY rowid",
                (user_id,),
            ).fetchall()
        # Same ordering contract as the in-memory store: invited_at, with
        # insertion order (rowid) as the stable tie-break.
        return sorted(
            (Sponsor.model_validate_json(row[0]) for row in rows),
            key=lambda s: s.invited_at,
        )

    def _transition(self, sponsor_id: str, target: SponsorStatus) -> Sponsor:
        # One transaction makes the read-check-write atomic: two racing
        # transitions serialize, and the loser sees the winner's status when
        # the legality check runs. ``get()`` is not reused here because the
        # shared database's transactions do not nest.
        with self._db.transaction() as cur:
            row = cur.execute(
                "SELECT payload FROM sponsors WHERE sponsor_id = ?",
                (sponsor_id,),
            ).fetchone()
            if row is None:
                raise SponsorNotFoundError(sponsor_id)
            current = Sponsor.model_validate_json(row[0])
            if not is_allowed_sponsor_transition(current.status, target):
                raise IllegalSponsorTransitionError(current.status, target)
            now = self._clock.now()
            updates: dict[str, object] = {"status": target, "updated_at": now}
            if target is SponsorStatus.ACCEPTED:
                updates["accepted_at"] = now
            elif target is SponsorStatus.REVOKED:
                updates["revoked_at"] = now
            # Re-validate through the model: ``model_copy(update=...)`` skips
            # ``model_validator`` checks, so a future partial ``updates`` could
            # silently produce a contract-violating row. ``model_validate`` of
            # the merged dump re-runs every status/timestamp invariant.
            updated = Sponsor.model_validate(current.model_dump() | updates)
            cur.execute(
                "UPDATE sponsors SET status = ?, payload = ? WHERE sponsor_id = ?",
                (updated.status.value, updated.model_dump_json(), sponsor_id),
            )
            return updated
