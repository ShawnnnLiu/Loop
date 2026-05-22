"""Tests for ``scheduler.windows.enumerate_free_windows``."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from agentic_calendar.scheduler.windows import enumerate_free_windows
from tests.scheduler._helpers import DEFAULT_POLICY, busy


def _start() -> datetime:
    return datetime(2026, 5, 4, 0, 0, 0, tzinfo=UTC)


def test_full_day_no_busy_yields_one_window() -> None:
    start = _start()
    windows = enumerate_free_windows(
        horizon_start=start,
        horizon_end=start + timedelta(days=1),
        free_busy=[],
        policy=DEFAULT_POLICY,
    )
    assert len(windows) == 1
    assert windows[0].duration_min == (22 * 60 + 30) - (8 * 60)


def test_busy_in_middle_splits_window() -> None:
    start = _start()
    busy_event = busy(
        datetime(2026, 5, 4, 12, 0, 0, tzinfo=UTC), minutes=60
    )
    windows = enumerate_free_windows(
        horizon_start=start,
        horizon_end=start + timedelta(days=1),
        free_busy=[busy_event],
        policy=DEFAULT_POLICY,
    )
    assert len(windows) == 2
    assert windows[0].duration_min == (12 - 8) * 60
    assert windows[1].duration_min == (22 * 60 + 30) - (13 * 60)


def test_weekend_excluded_when_disallowed() -> None:
    sat = datetime(2026, 5, 9, 0, 0, 0, tzinfo=UTC)
    no_weekends = DEFAULT_POLICY.model_copy(update={"allow_weekends": False})
    windows = enumerate_free_windows(
        horizon_start=sat,
        horizon_end=sat + timedelta(days=2),
        free_busy=[],
        policy=no_weekends,
    )
    assert windows == []


def test_horizon_clip_respects_end() -> None:
    start = _start()
    end = start + timedelta(hours=12)  # ends mid-day
    windows = enumerate_free_windows(
        horizon_start=start,
        horizon_end=end,
        free_busy=[],
        policy=DEFAULT_POLICY,
    )
    assert len(windows) == 1
    assert windows[0].end == end
