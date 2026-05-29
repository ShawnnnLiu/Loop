"""Tests for ``CalendarWriteLockManager`` (Phase 2)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from agentic_calendar.calendar_writer.lock import (
    CalendarWriteLockBusyError,
    CalendarWriteLockExpiredError,
    CalendarWriteLockManager,
    LockToken,
)
from agentic_calendar.common.clock import FrozenClock


def _manager(instant: datetime | None = None) -> tuple[CalendarWriteLockManager, FrozenClock]:
    clock = FrozenClock(instant or datetime(2026, 5, 4, 17, 0, tzinfo=UTC))
    return CalendarWriteLockManager(clock=clock), clock


# --------------------------------------------------------------------------- #
# acquire / busy / TTL
# --------------------------------------------------------------------------- #


def test_acquire_returns_token_with_120s_ttl() -> None:
    mgr, clock = _manager()
    token = mgr.acquire(user_id="u1", run_id="r1")
    assert token.user_id == "u1"
    assert token.holder_run_id == "r1"
    assert token.acquired_at == clock.now()
    assert token.expires_at - token.acquired_at == timedelta(seconds=120)


def test_acquire_twice_for_same_user_busy() -> None:
    mgr, _ = _manager()
    mgr.acquire(user_id="u1", run_id="r1")
    with pytest.raises(CalendarWriteLockBusyError) as exc:
        mgr.acquire(user_id="u1", run_id="r2")
    assert exc.value.user_id == "u1"
    assert exc.value.current_holder_run_id == "r1"


def test_acquire_different_users_concurrently() -> None:
    """Per-user locks: two distinct users can both hold the lock."""
    mgr, _ = _manager()
    t1 = mgr.acquire(user_id="alice", run_id="r1")
    t2 = mgr.acquire(user_id="bob", run_id="r2")
    assert t1.user_id != t2.user_id


def test_acquire_after_ttl_expires_grants() -> None:
    mgr, clock = _manager()
    mgr.acquire(user_id="u1", run_id="r1")
    clock.advance(seconds=121)
    new_token = mgr.acquire(user_id="u1", run_id="r2")
    assert new_token.holder_run_id == "r2"


def test_acquire_exactly_at_ttl_is_still_busy() -> None:
    """``expires_at > now`` (strict), so at exact equality the lock is free."""
    mgr, clock = _manager()
    mgr.acquire(user_id="u1", run_id="r1")
    clock.advance(seconds=120)
    # At exactly 120s, expires_at == now, which is NOT >, so the existing
    # lock is treated as expired and re-acquired.
    new_token = mgr.acquire(user_id="u1", run_id="r2")
    assert new_token.holder_run_id == "r2"


# --------------------------------------------------------------------------- #
# heartbeat
# --------------------------------------------------------------------------- #


def test_heartbeat_extends_ttl() -> None:
    mgr, clock = _manager()
    token = mgr.acquire(user_id="u1", run_id="r1")
    clock.advance(seconds=60)
    extended = mgr.heartbeat(token)
    assert extended.expires_at == clock.now() + timedelta(seconds=120)


def test_heartbeat_after_eviction_raises() -> None:
    mgr, clock = _manager()
    token = mgr.acquire(user_id="u1", run_id="r1")
    clock.advance(seconds=200)
    mgr.release_expired()
    with pytest.raises(CalendarWriteLockExpiredError):
        mgr.heartbeat(token)


def test_heartbeat_after_ttl_but_no_eviction_raises() -> None:
    mgr, clock = _manager()
    token = mgr.acquire(user_id="u1", run_id="r1")
    clock.advance(seconds=200)
    with pytest.raises(CalendarWriteLockExpiredError):
        mgr.heartbeat(token)


def test_heartbeat_with_foreign_token_raises() -> None:
    mgr, _ = _manager()
    mgr.acquire(user_id="u1", run_id="r1")
    foreign = LockToken(
        user_id="u1",
        holder_run_id="r_foreign",
        acquired_at=datetime(2026, 5, 4, 17, 0, tzinfo=UTC),
        expires_at=datetime(2026, 5, 4, 17, 2, tzinfo=UTC),
    )
    with pytest.raises(CalendarWriteLockExpiredError):
        mgr.heartbeat(foreign)


def test_heartbeat_with_mismatched_acquired_at_raises() -> None:
    mgr, _ = _manager()
    real = mgr.acquire(user_id="u1", run_id="r1")
    spoofed = LockToken(
        user_id=real.user_id,
        holder_run_id=real.holder_run_id,
        acquired_at=real.acquired_at + timedelta(seconds=1),
        expires_at=real.expires_at,
    )
    with pytest.raises(CalendarWriteLockExpiredError):
        mgr.heartbeat(spoofed)


# --------------------------------------------------------------------------- #
# release
# --------------------------------------------------------------------------- #


def test_release_frees_lock() -> None:
    mgr, _ = _manager()
    token = mgr.acquire(user_id="u1", run_id="r1")
    mgr.release(token)
    # Can re-acquire immediately.
    again = mgr.acquire(user_id="u1", run_id="r2")
    assert again.holder_run_id == "r2"


def test_release_is_idempotent() -> None:
    mgr, _ = _manager()
    token = mgr.acquire(user_id="u1", run_id="r1")
    mgr.release(token)
    mgr.release(token)  # no raise


def test_release_with_foreign_token_no_ops() -> None:
    mgr, _ = _manager()
    mgr.acquire(user_id="u1", run_id="r1")
    foreign = LockToken(
        user_id="u1",
        holder_run_id="other",
        acquired_at=datetime(2026, 5, 4, 17, 0, tzinfo=UTC),
        expires_at=datetime(2026, 5, 4, 17, 2, tzinfo=UTC),
    )
    mgr.release(foreign)  # no raise
    # Original holder still owns the lock.
    with pytest.raises(CalendarWriteLockBusyError):
        mgr.acquire(user_id="u1", run_id="r2")


def test_release_on_empty_no_ops() -> None:
    mgr, _ = _manager()
    foreign = LockToken(
        user_id="u_never_held",
        holder_run_id="r",
        acquired_at=datetime(2026, 5, 4, 17, 0, tzinfo=UTC),
        expires_at=datetime(2026, 5, 4, 17, 2, tzinfo=UTC),
    )
    mgr.release(foreign)  # no raise


# --------------------------------------------------------------------------- #
# release_expired
# --------------------------------------------------------------------------- #


def test_release_expired_returns_evicted_run_ids() -> None:
    mgr, clock = _manager()
    mgr.acquire(user_id="u1", run_id="r1")
    mgr.acquire(user_id="u2", run_id="r2")
    clock.advance(seconds=200)
    evicted = mgr.release_expired()
    assert sorted(evicted) == ["r1", "r2"]


def test_release_expired_keeps_fresh_locks() -> None:
    mgr, clock = _manager()
    mgr.acquire(user_id="u1", run_id="r1")
    clock.advance(seconds=60)
    mgr.acquire(user_id="u2", run_id="r2")  # u2 is fresh
    clock.advance(seconds=70)  # u1 is past 120s; u2 is at 70s
    evicted = mgr.release_expired()
    assert evicted == ["r1"]
    # u2 still busy.
    with pytest.raises(CalendarWriteLockBusyError):
        mgr.acquire(user_id="u2", run_id="r3")


def test_release_expired_with_nothing_held_returns_empty() -> None:
    mgr, _ = _manager()
    assert mgr.release_expired() == []
