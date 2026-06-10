"""Tests for the deterministic weekly check-in evaluator (golden scenario 21)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from agentic_calendar.accountability.checkin import (
    CheckinStatus,
    evaluate_checkin,
    most_recent_due_instant,
)
from agentic_calendar.contracts.common_types import Day

from ._builders import build_checkin_event, build_contract

LA = ZoneInfo("America/Los_Angeles")

#: Sunday 2026-05-10 19:00 in LA == 2026-05-11 02:00 UTC.
DUE_LOCAL = datetime(2026, 5, 10, 19, 0, tzinfo=LA)


def _checkin_contract(**overrides: object) -> object:
    return build_contract(
        weekly_checkin_enabled=True,
        weekly_checkin_day=Day.SUN,
        weekly_checkin_time="19:00",
        **overrides,
    )


def test_not_required_when_checkins_disabled() -> None:
    contract = build_contract(weekly_checkin_enabled=False)
    assessment = evaluate_checkin(contract, [], now=datetime(2026, 5, 11, 12, 0, tzinfo=UTC), tz=LA)
    assert assessment.status is CheckinStatus.NOT_REQUIRED
    assert assessment.due_at is None


def test_due_instant_is_most_recent_cadence_occurrence() -> None:
    contract = _checkin_contract()
    # Monday noon local: the most recent Sun 19:00 was yesterday evening.
    now = datetime(2026, 5, 11, 12, 0, tzinfo=LA)
    due = most_recent_due_instant(contract, now=now, tz=LA)
    assert due == DUE_LOCAL


def test_due_instant_wraps_to_previous_week_before_cadence_time() -> None:
    contract = _checkin_contract()
    # Sunday 18:00 local — this week's 19:00 has not arrived yet.
    now = datetime(2026, 5, 10, 18, 0, tzinfo=LA)
    due = most_recent_due_instant(contract, now=now, tz=LA)
    assert due == DUE_LOCAL - timedelta(days=7)


def test_due_within_grace_window() -> None:
    contract = _checkin_contract()
    now = DUE_LOCAL + timedelta(hours=12)
    assessment = evaluate_checkin(contract, [], now=now, tz=LA)
    assert assessment.status is CheckinStatus.DUE
    assert assessment.due_at == DUE_LOCAL


def test_missed_after_grace_window() -> None:
    contract = _checkin_contract()
    now = DUE_LOCAL + timedelta(hours=49)
    assessment = evaluate_checkin(contract, [], now=now, tz=LA)
    assert assessment.status is CheckinStatus.MISSED


def test_completed_when_event_submitted_after_due_instant() -> None:
    contract = _checkin_contract()
    event = build_checkin_event(created_at=DUE_LOCAL + timedelta(hours=1))
    now = DUE_LOCAL + timedelta(hours=12)
    assessment = evaluate_checkin(contract, [event], now=now, tz=LA)
    assert assessment.status is CheckinStatus.COMPLETED


def test_stale_event_does_not_silence_new_cycle() -> None:
    """A check-in for a prior cycle never answers the current one."""
    contract = _checkin_contract()
    stale = build_checkin_event(created_at=DUE_LOCAL - timedelta(days=6))
    now = DUE_LOCAL + timedelta(hours=12)
    assessment = evaluate_checkin(contract, [stale], now=now, tz=LA)
    assert assessment.status is CheckinStatus.DUE


def test_evaluation_is_timezone_correct() -> None:
    """The cadence is local time: the same UTC instant classifies by LA wall
    clock, not UTC wall clock."""
    contract = _checkin_contract()
    # 2026-05-11 01:00 UTC is Sunday 18:00 in LA — before this week's due.
    now = datetime(2026, 5, 11, 1, 0, tzinfo=UTC)
    due = most_recent_due_instant(contract, now=now, tz=LA)
    assert due == DUE_LOCAL - timedelta(days=7)


def test_same_inputs_same_assessment() -> None:
    """Deterministic replay: identical inputs, identical assessment."""
    contract = _checkin_contract()
    now = DUE_LOCAL + timedelta(hours=12)
    a = evaluate_checkin(contract, [], now=now, tz=LA)
    b = evaluate_checkin(contract, [], now=now, tz=LA)
    assert a == b
