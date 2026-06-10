"""Tests for the accountability-state projection (spec formulas + thresholds)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from agentic_calendar.accountability.checkin import CheckinStatus
from agentic_calendar.accountability.projection import (
    ProjectionInput,
    behind_schedule_percent,
    project_accountability_state,
)
from agentic_calendar.common.clock import FrozenClock
from agentic_calendar.contracts.common_types import AccountabilityStatus

from ._builders import build_contract, build_telemetry_event

T = datetime(2026, 5, 10, 20, 0, tzinfo=UTC)
CLOCK = FrozenClock(T)


def _events(completed: int, missed: int, *, prefix: str = "t", reschedules: int = 0):
    evs = [
        build_telemetry_event(f"{prefix}_done_{i}", user_reschedule_count=reschedules)
        for i in range(completed)
    ]
    evs += [build_telemetry_event(f"{prefix}_miss_{i}", completed=False) for i in range(missed)]
    return evs


def _project(
    *,
    events_7d=(),
    events_14d=None,
    scheduled_due: int = 360,
    completed_due: int = 360,
    contract=None,
    checkin_status: CheckinStatus = CheckinStatus.NOT_REQUIRED,
):
    events_7d = list(events_7d)
    events_14d = list(events_7d) if events_14d is None else list(events_14d)
    return project_accountability_state(
        ProjectionInput(
            user_id="user_123",
            plan_id="plan_004",
            events_7d=events_7d,
            events_14d=events_14d,
            scheduled_minutes_due=scheduled_due,
            completed_minutes_due=completed_due,
        ),
        contract or build_contract(),
        checkin_status,
        clock=CLOCK,
    )


# -- behind-schedule formula ----------------------------------------------------


@pytest.mark.parametrize(
    ("scheduled", "completed", "expected"),
    [
        (360, 360, 0),
        (360, 295, 18),  # axiom 21 example neighborhood: round-half-up
        (360, 270, 25),
        (360, 0, 100),
        (0, 0, 0),  # nothing due yet → not behind
        (360, 420, 0),  # overshoot clamps at zero
        (200, 99, 51),  # 50.5 rounds half-up to 51
    ],
)
def test_behind_schedule_formula(scheduled: int, completed: int, expected: int) -> None:
    assert (
        behind_schedule_percent(scheduled_minutes_due=scheduled, completed_minutes_due=completed)
        == expected
    )


# -- window metrics ---------------------------------------------------------------


def test_completion_rates_and_missed_counts() -> None:
    week = _events(4, 2)
    fortnight = week + _events(2, 4, prefix="old")
    state = _project(events_7d=week, events_14d=fortnight)
    assert state.completion_rate_7d == 0.67
    assert state.completion_rate_14d == 0.5
    assert state.missed_tasks_7d == 2


def test_empty_windows_read_as_no_evidence() -> None:
    state = _project()
    assert state.completion_rate_7d == 1.0
    assert state.completion_rate_14d == 1.0
    assert state.current_status is AccountabilityStatus.ON_TRACK


def test_reschedule_count_sums_over_window() -> None:
    events = [
        build_telemetry_event("t1", user_reschedule_count=3),
        build_telemetry_event("t2", user_reschedule_count=1),
    ]
    state = _project(events_7d=events)
    assert state.reschedule_count_7d == 4


def test_nested_window_invariant_enforced() -> None:
    with pytest.raises(ValueError, match="nested windows"):
        _project(events_7d=_events(3, 0), events_14d=_events(1, 0))


# -- status thresholds (spec table, T=20) -----------------------------------------


def test_status_on_track() -> None:
    state = _project(scheduled_due=360, completed_due=340)  # 6% behind, no misses
    assert state.current_status is AccountabilityStatus.ON_TRACK


def test_status_slightly_behind_via_percent_band() -> None:
    state = _project(scheduled_due=360, completed_due=295)  # 18% ≥ ceil(20/2)
    assert state.current_status is AccountabilityStatus.SLIGHTLY_BEHIND


def test_status_slightly_behind_via_single_miss() -> None:
    state = _project(events_7d=_events(5, 1), completed_due=360)
    assert state.current_status is AccountabilityStatus.SLIGHTLY_BEHIND


def test_status_behind_at_threshold() -> None:
    state = _project(scheduled_due=360, completed_due=270)  # 25% ≥ 20
    assert state.current_status is AccountabilityStatus.BEHIND


def test_status_far_behind_at_double_threshold() -> None:
    state = _project(scheduled_due=360, completed_due=200)  # 44% ≥ 40
    assert state.current_status is AccountabilityStatus.FAR_BEHIND


def test_status_disengaged_overrides_percent() -> None:
    fortnight = _events(1, 9)  # 0.1 completion over 14d
    state = _project(events_7d=[], events_14d=fortnight, completed_due=340)
    assert state.current_status is AccountabilityStatus.DISENGAGED


# -- axiom 21 worked example -------------------------------------------------------


def test_axiom_21_example_classifies_slightly_behind() -> None:
    """behind 18%, 3 missed, rate_14d ≈ 0.55, T=20 → slightly_behind."""
    week = _events(5, 3)
    fortnight = week + _events(3, 5, prefix="old")
    state = _project(
        events_7d=week,
        events_14d=fortnight,
        scheduled_due=360,
        completed_due=295,
        checkin_status=CheckinStatus.DUE,
    )
    assert state.behind_schedule_percent == 18
    assert state.current_status is AccountabilityStatus.SLIGHTLY_BEHIND
    assert state.weekly_checkin_completed is False


def test_projection_never_mutates_only_recomputes() -> None:
    """Same inputs, same state — and the object is frozen."""
    week = _events(4, 2)
    a = _project(events_7d=week)
    b = _project(events_7d=week)
    assert a == b
