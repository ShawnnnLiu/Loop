"""In-memory sponsor store with lifecycle-transition enforcement (Phase 3).

Persistence-backed implementations land in a later phase. The Phase 3 in-memory
version follows the same concurrency shape as
:class:`agentic_calendar.approval.store.InMemoryApprovalEventStore`.

Unlike approval events, a :class:`Sponsor` row is *mutable at the status level*:
the invite lifecycle (``pending`` → ``accepted`` → ``revoked``) advances over
time. The store is the authority for transition legality — it rejects any
transition not permitted by ``ALLOWED_SPONSOR_TRANSITIONS`` so that no caller can
reactivate a revoked sponsor or skip acceptance (spec "Invite Lifecycle").
Each transition writes a new frozen :class:`Sponsor` instance; the model itself
never mutates in place.
"""

from __future__ import annotations

import threading
from typing import Protocol, runtime_checkable

from agentic_calendar.common.clock import Clock
from agentic_calendar.common.errors import AgenticCalendarError
from agentic_calendar.contracts.sponsor import (
    Sponsor,
    SponsorStatus,
    is_allowed_sponsor_transition,
)


class SponsorStoreError(AgenticCalendarError):
    """Base for sponsor-store errors that callers may catch."""


class SponsorAlreadyExistsError(SponsorStoreError):
    """Attempted to invite a ``sponsor_id`` that already exists."""


class SponsorNotFoundError(SponsorStoreError):
    pass


class IllegalSponsorTransitionError(SponsorStoreError):
    """A requested status transition is not permitted by the lifecycle.

    Carries the attempted ``from``/``to`` so callers can surface a precise
    message (e.g. trying to accept an already-revoked sponsor).
    """

    def __init__(self, current: SponsorStatus, requested: SponsorStatus) -> None:
        self.current = current
        self.requested = requested
        super().__init__(f"illegal sponsor transition {current.value!r} -> {requested.value!r}")


@runtime_checkable
class SponsorStore(Protocol):
    """Read/write surface for sponsor rows."""

    def invite(self, sponsor: Sponsor) -> None: ...

    def get(self, sponsor_id: str) -> Sponsor: ...

    def accept(self, sponsor_id: str) -> Sponsor: ...

    def revoke(self, sponsor_id: str) -> Sponsor: ...

    def list_for_user(self, user_id: str) -> list[Sponsor]: ...


class InMemorySponsorStore:
    """Default Phase 3 store. Thread-safe, ephemeral, non-persistent."""

    def __init__(self, clock: Clock) -> None:
        self._clock = clock
        self._by_id: dict[str, Sponsor] = {}
        # Must stay an RLock: ``_transition`` calls ``get()`` while already
        # holding the lock. A plain Lock would self-deadlock.
        self._lock = threading.RLock()

    def invite(self, sponsor: Sponsor) -> None:
        """Insert a new sponsor row. Rejects an existing ``sponsor_id``."""
        with self._lock:
            if sponsor.sponsor_id in self._by_id:
                raise SponsorAlreadyExistsError(sponsor.sponsor_id)
            self._by_id[sponsor.sponsor_id] = sponsor

    def get(self, sponsor_id: str) -> Sponsor:
        with self._lock:
            if sponsor_id not in self._by_id:
                raise SponsorNotFoundError(sponsor_id)
            return self._by_id[sponsor_id]

    def accept(self, sponsor_id: str) -> Sponsor:
        """Transition ``pending → accepted`` and stamp ``accepted_at``."""
        return self._transition(sponsor_id, SponsorStatus.ACCEPTED)

    def revoke(self, sponsor_id: str) -> Sponsor:
        """Transition ``pending|accepted → revoked`` and stamp ``revoked_at``.

        Revocation takes effect immediately so the next generated report sees
        the new status (spec "Invite Lifecycle")."""
        return self._transition(sponsor_id, SponsorStatus.REVOKED)

    def list_for_user(self, user_id: str) -> list[Sponsor]:
        with self._lock:
            return sorted(
                (s for s in self._by_id.values() if s.user_id == user_id),
                key=lambda s: s.invited_at,
            )

    def _transition(self, sponsor_id: str, target: SponsorStatus) -> Sponsor:
        with self._lock:
            current = self.get(sponsor_id)
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
            self._by_id[sponsor_id] = updated
            return updated
