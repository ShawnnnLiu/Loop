"""SQLite consent store (Phase 9a).

Persistent twin of :class:`agentic_calendar.consent.store.InMemoryConsentStore`:
same :class:`~agentic_calendar.consent.store.ConsentStore` protocol, same error
types, same lifecycle invariants (spec "Lifecycle"):

* the only legal transition is ``granted → revoked`` (``revoked`` is
  terminal; re-consent is a **new** record, never a reactivation);
* at most one record per ``(user_id, scope)`` is in ``granted`` status at a
  time.

Rows hold the canonical Pydantic JSON dump plus the key columns needed for
lookups; reads rebuild the frozen model with ``model_validate_json`` so a
round trip is contract-validated, never trusted. The ``status`` column is
kept in sync with the payload on every write so the single-active-grant
check stays a pure SQL predicate. ``delete_for_user`` exists for the
data-delete control (ADR-0007): a user's right to erase their consent
history is exercised through the audited data-control path, never silently.
"""

from __future__ import annotations

from agentic_calendar.common.clock import Clock
from agentic_calendar.common.sqlite import SqliteDatabase
from agentic_calendar.contracts.consent_record import (
    ConsentRecord,
    ConsentScope,
    ConsentStatus,
    is_allowed_consent_transition,
)

from .store import (
    ConsentAlreadyGrantedError,
    ConsentRecordAlreadyExistsError,
    ConsentRecordNotFoundError,
    IllegalConsentTransitionError,
    NonGrantedConsentInsertError,
)

_SCHEMA_COMPONENT = "consent.consent_records"
_SCHEMA_VERSION = 1
_SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS consent_records (
        consent_record_id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        scope TEXT NOT NULL,
        status TEXT NOT NULL,
        payload TEXT NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_consent_records_user_scope
        ON consent_records (user_id, scope)
    """,
)


class SqliteConsentStore:
    """Persistent consent store. Thread-safe via the shared database lock."""

    def __init__(self, db: SqliteDatabase, clock: Clock) -> None:
        self._db = db
        self._clock = clock
        db.ensure_schema(_SCHEMA_COMPONENT, version=_SCHEMA_VERSION, statements=_SCHEMA)

    def grant(self, record: ConsentRecord) -> None:
        """Insert a new granted record.

        Rejects an existing ``consent_record_id``, a record not in
        ``granted`` status, and a duplicate active grant for the same
        ``(user_id, scope)``.
        """
        if record.status is not ConsentStatus.GRANTED:
            raise NonGrantedConsentInsertError(record.consent_record_id)
        self.load(record)

    def load(self, record: ConsentRecord) -> None:
        """Rehydrate one pre-existing record (any status) from persistence.

        Composition roots use this to seed prior consent history (including
        revoked rows, which ``grant`` rightly refuses to insert). Not part of
        the :class:`~agentic_calendar.consent.store.ConsentStore` protocol —
        live state changes still go through ``grant``/``revoke`` only.
        Enforces the same id-uniqueness and single-active-grant invariants as
        ``grant``, with both checks and the insert in one transaction (the
        kernel's transactions do not nest, so the active-grant check is an
        inline SELECT rather than a ``get_active`` call).
        """
        with self._db.transaction() as cur:
            row = cur.execute(
                "SELECT 1 FROM consent_records WHERE consent_record_id = ?",
                (record.consent_record_id,),
            ).fetchone()
            if row is not None:
                raise ConsentRecordAlreadyExistsError(record.consent_record_id)
            if record.status is ConsentStatus.GRANTED:
                active = cur.execute(
                    "SELECT 1 FROM consent_records"
                    " WHERE user_id = ? AND scope = ? AND status = ?"
                    " LIMIT 1",
                    (
                        record.user_id,
                        record.scope.value,
                        ConsentStatus.GRANTED.value,
                    ),
                ).fetchone()
                if active is not None:
                    raise ConsentAlreadyGrantedError(record.user_id, record.scope)
            cur.execute(
                "INSERT INTO consent_records"
                " (consent_record_id, user_id, scope, status, payload)"
                " VALUES (?, ?, ?, ?, ?)",
                (
                    record.consent_record_id,
                    record.user_id,
                    record.scope.value,
                    record.status.value,
                    record.model_dump_json(),
                ),
            )

    def get(self, consent_record_id: str) -> ConsentRecord:
        with self._db.read() as cur:
            row = cur.execute(
                "SELECT payload FROM consent_records WHERE consent_record_id = ?",
                (consent_record_id,),
            ).fetchone()
        if row is None:
            raise ConsentRecordNotFoundError(consent_record_id)
        return ConsentRecord.model_validate_json(row[0])

    def revoke(self, consent_record_id: str) -> ConsentRecord:
        """Transition ``granted → revoked`` and stamp ``revoked_at``.

        Revocation takes effect immediately: the next gate check — training
        or serving — sees the revoked row (spec "Lifecycle"). Lookup,
        transition check, and the row update share one transaction so two
        racing revokes serialize to exactly one winner — the same atomicity
        the in-memory store's lock provides.
        """
        with self._db.transaction() as cur:
            row = cur.execute(
                "SELECT payload FROM consent_records WHERE consent_record_id = ?",
                (consent_record_id,),
            ).fetchone()
            if row is None:
                raise ConsentRecordNotFoundError(consent_record_id)
            current = ConsentRecord.model_validate_json(row[0])
            if not is_allowed_consent_transition(current.status, ConsentStatus.REVOKED):
                raise IllegalConsentTransitionError(current.status, ConsentStatus.REVOKED)
            now = self._clock.now()
            updates: dict[str, object] = {
                "status": ConsentStatus.REVOKED,
                "revoked_at": now,
                "updated_at": now,
            }
            # Re-validate through the model: ``model_copy(update=...)`` skips
            # ``model_validator`` checks, so a future partial ``updates`` could
            # silently produce a contract-violating row. ``model_validate`` of
            # the merged dump re-runs every status/timestamp invariant.
            updated = ConsentRecord.model_validate(current.model_dump() | updates)
            cur.execute(
                "UPDATE consent_records SET status = ?, payload = ?"
                " WHERE consent_record_id = ?",
                (
                    updated.status.value,
                    updated.model_dump_json(),
                    consent_record_id,
                ),
            )
            return updated

    def get_active(self, user_id: str, scope: ConsentScope) -> ConsentRecord | None:
        """Return the single ``granted`` record for ``(user_id, scope)``, if any."""
        with self._db.read() as cur:
            row = cur.execute(
                "SELECT payload FROM consent_records"
                " WHERE user_id = ? AND scope = ? AND status = ?"
                " ORDER BY rowid LIMIT 1",
                (user_id, scope.value, ConsentStatus.GRANTED.value),
            ).fetchone()
        return ConsentRecord.model_validate_json(row[0]) if row else None

    def latest_for_scope(self, user_id: str, scope: ConsentScope) -> ConsentRecord | None:
        """Return the most recently inserted record for ``(user_id, scope)``.

        The gate uses this to distinguish "never consented"
        (``CONSENT_MISSING``) from "consented, then revoked"
        (``CONSENT_REVOKED``).
        """
        with self._db.read() as cur:
            row = cur.execute(
                "SELECT payload FROM consent_records"
                " WHERE user_id = ? AND scope = ?"
                " ORDER BY rowid DESC LIMIT 1",
                (user_id, scope.value),
            ).fetchone()
        return ConsentRecord.model_validate_json(row[0]) if row else None

    def list_for_user(self, user_id: str) -> list[ConsentRecord]:
        with self._db.read() as cur:
            rows = cur.execute(
                "SELECT payload FROM consent_records WHERE user_id = ?"
                " ORDER BY rowid",
                (user_id,),
            ).fetchall()
        return [ConsentRecord.model_validate_json(row[0]) for row in rows]

    def delete_for_user(self, user_id: str) -> int:
        """Remove every record for ``user_id``; return the count removed."""
        with self._db.transaction() as cur:
            cur.execute(
                "DELETE FROM consent_records WHERE user_id = ?",
                (user_id,),
            )
            return cur.rowcount
