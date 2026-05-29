"""Per-user calendar write lock.

Spec: axiom 06 lines 236-247 + axiom 13. One in-flight write per user, TTL
120 seconds, heartbeat extension while the write is making progress, automatic
release on TTL expiry, hourly cleanup of zombie locks via
:meth:`CalendarWriteLockManager.release_expired`.

The lock is in-process for Phase 2; a distributed implementation can wrap
this same interface in a later phase. The clock is injected via
:class:`agentic_calendar.common.clock.Clock` so tests advance time
deterministically.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import ClassVar

from agentic_calendar.common.clock import Clock
from agentic_calendar.common.errors import AgenticCalendarError


@dataclass(frozen=True, slots=True)
class LockToken:
    """Opaque proof-of-acquisition returned by :meth:`CalendarWriteLockManager.acquire`."""

    user_id: str
    holder_run_id: str
    acquired_at: datetime
    expires_at: datetime


class CalendarWriteLockBusyError(AgenticCalendarError):
    """Another in-flight write already holds the lock for this user."""

    def __init__(self, user_id: str, current_holder_run_id: str) -> None:
        super().__init__(
            f"calendar write lock for user_id={user_id!r} held by "
            f"run_id={current_holder_run_id!r}"
        )
        self.user_id = user_id
        self.current_holder_run_id = current_holder_run_id


class CalendarWriteLockExpiredError(AgenticCalendarError):
    """The lock token's TTL elapsed (or a cleanup eviction took it).

    The manager maps this to ``ReasonCode.CALENDAR_WRITE_LOCK_EXPIRED`` and
    treats the run as ``EXTERNAL_SYNC_FAILED`` per axiom 06 lines 224-232.
    """


class CalendarWriteLockManager:
    """Single-process per-user calendar write lock manager."""

    TTL_SECONDS: ClassVar[int] = 120

    def __init__(self, *, clock: Clock) -> None:
        self._clock = clock
        self._tokens: dict[str, LockToken] = {}
        self._lock = threading.RLock()

    def acquire(self, *, user_id: str, run_id: str) -> LockToken:
        """Acquire the lock for ``user_id`` on behalf of ``run_id``.

        If an existing token is past its ``expires_at``, it is implicitly
        evicted and the lock is re-granted. Otherwise raises
        :class:`CalendarWriteLockBusyError`.
        """
        now = self._clock.now()
        with self._lock:
            existing = self._tokens.get(user_id)
            if existing is not None and existing.expires_at > now:
                raise CalendarWriteLockBusyError(user_id, existing.holder_run_id)
            token = LockToken(
                user_id=user_id,
                holder_run_id=run_id,
                acquired_at=now,
                expires_at=now + timedelta(seconds=self.TTL_SECONDS),
            )
            self._tokens[user_id] = token
            return token

    def heartbeat(self, token: LockToken) -> LockToken:
        """Extend the lock's TTL while a write is actively progressing.

        Raises :class:`CalendarWriteLockExpiredError` if the token has been
        evicted (TTL expired or cleanup ran). Foreign tokens (same user but
        different ``holder_run_id``) also raise.
        """
        now = self._clock.now()
        with self._lock:
            current = self._tokens.get(token.user_id)
            if (
                current is None
                or current.holder_run_id != token.holder_run_id
                or current.acquired_at != token.acquired_at
                or current.expires_at <= now
            ):
                raise CalendarWriteLockExpiredError(
                    f"calendar write lock for user_id={token.user_id!r} "
                    f"run_id={token.holder_run_id!r} is no longer held"
                )
            new_token = LockToken(
                user_id=token.user_id,
                holder_run_id=token.holder_run_id,
                acquired_at=token.acquired_at,
                expires_at=now + timedelta(seconds=self.TTL_SECONDS),
            )
            self._tokens[token.user_id] = new_token
            return new_token

    def release(self, token: LockToken) -> None:
        """Release the lock. Idempotent; no-ops on foreign/expired tokens."""
        with self._lock:
            current = self._tokens.get(token.user_id)
            if current is None:
                return
            if (
                current.holder_run_id == token.holder_run_id
                and current.acquired_at == token.acquired_at
            ):
                del self._tokens[token.user_id]

    def release_expired(self) -> list[str]:
        """Evict every token whose ``expires_at`` is at or before ``clock.now()``.

        Returns the list of ``holder_run_id`` values that were evicted, so the
        hourly cleanup caller can mark each run ``external_sync_failed`` per
        axiom 06 lines 243-247. Deployment of the hourly trigger is out of
        scope for Phase 2.
        """
        now = self._clock.now()
        evicted: list[str] = []
        with self._lock:
            for user_id, token in list(self._tokens.items()):
                if token.expires_at <= now:
                    evicted.append(token.holder_run_id)
                    del self._tokens[user_id]
        return evicted
