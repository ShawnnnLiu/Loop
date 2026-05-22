"""Tests for ``agentic_calendar.common.clock``."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from agentic_calendar.common.clock import Clock, FrozenClock, SystemClock


def test_system_clock_returns_aware_datetime() -> None:
    clock = SystemClock()
    now = clock.now()
    assert now.tzinfo is not None
    assert now.utcoffset() == timedelta(0)


def test_system_clock_satisfies_protocol() -> None:
    assert isinstance(SystemClock(), Clock)


def test_frozen_clock_returns_fixed_instant() -> None:
    instant = datetime(2026, 5, 4, 12, 0, 0, tzinfo=UTC)
    clock = FrozenClock(instant)
    assert clock.now() == instant
    assert clock.now() == instant


def test_frozen_clock_advance_steps_forward() -> None:
    clock = FrozenClock(datetime(2026, 5, 4, 12, 0, 0, tzinfo=UTC))
    clock.advance(minutes=30)
    assert clock.now() == datetime(2026, 5, 4, 12, 30, 0, tzinfo=UTC)
    clock.advance(hours=1, seconds=15)
    assert clock.now() == datetime(2026, 5, 4, 13, 30, 15, tzinfo=UTC)


def test_frozen_clock_rejects_naive_datetime() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        FrozenClock(datetime(2026, 5, 4, 12, 0, 0))


def test_frozen_clock_satisfies_protocol() -> None:
    assert isinstance(
        FrozenClock(datetime(2026, 5, 4, 12, 0, 0, tzinfo=UTC)), Clock
    )
