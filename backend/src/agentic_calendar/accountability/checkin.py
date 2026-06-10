"""Deterministic weekly check-in evaluator (Phase 7).

Spec: ``docs/specs/checkin-event.schema.md``, axiom 21 ("Weekly Check-In
Schema"). Golden scenario 21.

Whether a check-in is due or missed is computed, never stored: from the
accountability contract's cadence (``weekly_checkin_day`` +
``weekly_checkin_time`` in the user's timezone), the injected clock, and the
presence of a :class:`CheckinEvent` submitted at or after the most recent due
instant. The grace window between ``CHECKIN_DUE`` and ``CHECKIN_MISSED`` is
the contract's ``checkin_grace_hours`` (heuristic prior, default 48h).

The user's timezone is caller-supplied (the profile owns timezone semantics;
this module never guesses one).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, time, timedelta, tzinfo
from enum import StrEnum

from agentic_calendar.contracts.accountability_contract import AccountabilityContract
from agentic_calendar.contracts.checkin_event import CheckinEvent
from agentic_calendar.contracts.common_types import Day

_DAY_TO_WEEKDAY: dict[Day, int] = {
    Day.MON: 0,
    Day.TUE: 1,
    Day.WED: 2,
    Day.THU: 3,
    Day.FRI: 4,
    Day.SAT: 5,
    Day.SUN: 6,
}


class CheckinStatus(StrEnum):
    """Deterministic check-in position for the current cycle."""

    NOT_REQUIRED = "not_required"
    COMPLETED = "completed"
    DUE = "due"
    MISSED = "missed"


@dataclass(frozen=True)
class CheckinAssessment:
    """Status plus the due instant that produced it (None when not required)."""

    status: CheckinStatus
    due_at: datetime | None


def most_recent_due_instant(
    contract: AccountabilityContract, *, now: datetime, tz: tzinfo
) -> datetime | None:
    """Return the latest cadence instant at or before ``now``, or None.

    The cadence is interpreted in the user's timezone: "Sun 19:00" means
    19:00 local, whatever UTC instant that is.
    """
    if not contract.weekly_checkin_enabled:
        return None
    # The contract validator guarantees day/time are set when enabled.
    assert contract.weekly_checkin_day is not None
    assert contract.weekly_checkin_time is not None

    now_local = now.astimezone(tz)
    hour, minute = (int(p) for p in contract.weekly_checkin_time.split(":"))
    days_back = (now_local.weekday() - _DAY_TO_WEEKDAY[contract.weekly_checkin_day]) % 7
    candidate = datetime.combine(
        now_local.date() - timedelta(days=days_back),
        time(hour, minute),
        tzinfo=tz,
    )
    if candidate > now_local:
        candidate -= timedelta(days=7)
    return candidate


def evaluate_checkin(
    contract: AccountabilityContract,
    events: Sequence[CheckinEvent],
    *,
    now: datetime,
    tz: tzinfo,
) -> CheckinAssessment:
    """Classify the current cycle's check-in position.

    ``events`` must already be scoped to one user and plan by the caller (the
    ``DriftInput`` convention). A check-in *counts* for the cycle when it was
    submitted at or after the cycle's due instant — answering early for a
    cycle that has not come due yet does not silence a later cycle.
    """
    due_at = most_recent_due_instant(contract, now=now, tz=tz)
    if due_at is None:
        return CheckinAssessment(status=CheckinStatus.NOT_REQUIRED, due_at=None)

    if any(e.created_at >= due_at for e in events):
        return CheckinAssessment(status=CheckinStatus.COMPLETED, due_at=due_at)

    if now.astimezone(tz) < due_at + timedelta(hours=contract.checkin_grace_hours):
        return CheckinAssessment(status=CheckinStatus.DUE, due_at=due_at)
    return CheckinAssessment(status=CheckinStatus.MISSED, due_at=due_at)
