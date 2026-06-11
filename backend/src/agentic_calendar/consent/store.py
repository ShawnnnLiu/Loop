"""In-memory consent store with lifecycle-transition enforcement (Phase 6a).

Persistence-backed implementations land in a later phase. The in-memory
version follows the same concurrency shape as
:class:`agentic_calendar.accountability.sponsor_store.InMemorySponsorStore`.

The store is the authority for two invariants the contract model cannot see
on its own (spec "Lifecycle"):

* the only legal transition is ``granted → revoked`` (``revoked`` is
  terminal; re-consent is a **new** record, never a reactivation);
* at most one record per ``(user_id, scope)`` is in ``granted`` status at a
  time.

Each transition writes a new frozen :class:`ConsentRecord` instance; the
model itself never mutates in place. ``delete_for_user`` exists for the
data-delete control (ADR-0007): a user's right to erase their consent
history is exercised through the audited data-control path, never silently.
"""

from __future__ import annotations

import threading
from typing import Protocol, runtime_checkable

from agentic_calendar.common.clock import Clock
from agentic_calendar.common.errors import AgenticCalendarError
from agentic_calendar.contracts.consent_record import (
    ConsentRecord,
    ConsentScope,
    ConsentStatus,
    is_allowed_consent_transition,
)


class ConsentStoreError(AgenticCalendarError):
    """Base for consent-store errors that callers may catch."""


class ConsentRecordAlreadyExistsError(ConsentStoreError):
    """Attempted to insert a ``consent_record_id`` that already exists."""


class ConsentRecordNotFoundError(ConsentStoreError):
    pass


class ConsentAlreadyGrantedError(ConsentStoreError):
    """An active grant already exists for this ``(user_id, scope)``."""

    def __init__(self, user_id: str, scope: ConsentScope) -> None:
        self.user_id = user_id
        self.scope = scope
        super().__init__(f"active {scope.value!r} consent already exists for {user_id!r}")


class NonGrantedConsentInsertError(ConsentStoreError):
    """``grant`` only inserts records in ``granted`` status.

    A revoked record can only come into existence through the ``revoke``
    transition, so the store's history is always a faithful lifecycle replay.
    """


class IllegalConsentTransitionError(ConsentStoreError):
    """A requested status transition is not permitted by the lifecycle.

    Carries the attempted ``from``/``to`` so callers can surface a precise
    message (e.g. trying to revoke an already-revoked record).
    """

    def __init__(self, current: ConsentStatus, requested: ConsentStatus) -> None:
        self.current = current
        self.requested = requested
        super().__init__(f"illegal consent transition {current.value!r} -> {requested.value!r}")


@runtime_checkable
class ConsentStore(Protocol):
    """Read/write surface for consent records."""

    def grant(self, record: ConsentRecord) -> None: ...

    def get(self, consent_record_id: str) -> ConsentRecord: ...

    def revoke(self, consent_record_id: str) -> ConsentRecord: ...

    def get_active(self, user_id: str, scope: ConsentScope) -> ConsentRecord | None: ...

    def latest_for_scope(self, user_id: str, scope: ConsentScope) -> ConsentRecord | None: ...

    def list_for_user(self, user_id: str) -> list[ConsentRecord]: ...

    def delete_for_user(self, user_id: str) -> int: ...


class InMemoryConsentStore:
    """Default Phase 6a store. Thread-safe, ephemeral, non-persistent."""

    def __init__(self, clock: Clock) -> None:
        self._clock = clock
        self._by_id: dict[str, ConsentRecord] = {}
        self._order: list[str] = []
        # Must stay an RLock: ``revoke`` calls ``get()`` while already
        # holding the lock. A plain Lock would self-deadlock.
        self._lock = threading.RLock()

    def grant(self, record: ConsentRecord) -> None:
        """Insert a new granted record.

        Rejects an existing ``consent_record_id``, a record not in
        ``granted`` status, and a duplicate active grant for the same
        ``(user_id, scope)``.
        """
        with self._lock:
            if record.status is not ConsentStatus.GRANTED:
                raise NonGrantedConsentInsertError(record.consent_record_id)
            self.load(record)

    def load(self, record: ConsentRecord) -> None:
        """Rehydrate one pre-existing record (any status) from persistence.

        Composition roots use this to seed prior consent history (including
        revoked rows, which ``grant`` rightly refuses to insert). Not part of
        the :class:`ConsentStore` protocol — live state changes still go
        through ``grant``/``revoke`` only. Enforces the same id-uniqueness
        and single-active-grant invariants as ``grant``.
        """
        with self._lock:
            if record.consent_record_id in self._by_id:
                raise ConsentRecordAlreadyExistsError(record.consent_record_id)
            if (
                record.status is ConsentStatus.GRANTED
                and self.get_active(record.user_id, record.scope) is not None
            ):
                raise ConsentAlreadyGrantedError(record.user_id, record.scope)
            self._by_id[record.consent_record_id] = record
            self._order.append(record.consent_record_id)

    def get(self, consent_record_id: str) -> ConsentRecord:
        with self._lock:
            if consent_record_id not in self._by_id:
                raise ConsentRecordNotFoundError(consent_record_id)
            return self._by_id[consent_record_id]

    def revoke(self, consent_record_id: str) -> ConsentRecord:
        """Transition ``granted → revoked`` and stamp ``revoked_at``.

        Revocation takes effect immediately: the next gate check — training
        or serving — sees the revoked row (spec "Lifecycle").
        """
        with self._lock:
            current = self.get(consent_record_id)
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
            self._by_id[consent_record_id] = updated
            return updated

    def get_active(self, user_id: str, scope: ConsentScope) -> ConsentRecord | None:
        """Return the single ``granted`` record for ``(user_id, scope)``, if any."""
        with self._lock:
            for record_id in self._order:
                record = self._by_id[record_id]
                if (
                    record.user_id == user_id
                    and record.scope is scope
                    and record.status is ConsentStatus.GRANTED
                ):
                    return record
            return None

    def latest_for_scope(self, user_id: str, scope: ConsentScope) -> ConsentRecord | None:
        """Return the most recently inserted record for ``(user_id, scope)``.

        The gate uses this to distinguish "never consented"
        (``CONSENT_MISSING``) from "consented, then revoked"
        (``CONSENT_REVOKED``).
        """
        with self._lock:
            latest: ConsentRecord | None = None
            for record_id in self._order:
                record = self._by_id[record_id]
                if record.user_id == user_id and record.scope is scope:
                    latest = record
            return latest

    def list_for_user(self, user_id: str) -> list[ConsentRecord]:
        with self._lock:
            return [self._by_id[i] for i in self._order if self._by_id[i].user_id == user_id]

    def delete_for_user(self, user_id: str) -> int:
        """Remove every record for ``user_id``; return the count removed."""
        with self._lock:
            doomed = [i for i in self._order if self._by_id[i].user_id == user_id]
            for record_id in doomed:
                del self._by_id[record_id]
            self._order = [i for i in self._order if i not in set(doomed)]
            return len(doomed)
