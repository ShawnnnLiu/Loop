"""Tests for deterministic telemetry metrics (Phase 4)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from agentic_calendar.contracts.telemetry import DataQuality, TelemetryEvent
from agentic_calendar.telemetry import metrics

TS = datetime(2026, 5, 6, tzinfo=UTC)


def _ev(
    tid: str,
    *,
    sched: int = 90,
    actual: int | None = 90,
    completed: bool = True,
    reschedule: int = 0,
    estimated: bool = False,
    dq: DataQuality = DataQuality.COMPLETE,
) -> TelemetryEvent:
    return TelemetryEvent(
        telemetry_event_id=f"tel_{tid}",
        task_id=tid,
        scheduled_duration_min=sched,
        actual_duration_min=actual if completed else None,
        completed=completed,
        completion_timestamp=TS if completed else None,
        user_reschedule_count=reschedule,
        data_quality=dq,
        duration_estimated=estimated,
    )


def test_completion_rate_basic_and_empty() -> None:
    events = [_ev(f"t{i}", completed=(i < 7)) for i in range(10)]
    assert metrics.completion_rate(events) == 0.7
    assert metrics.completion_rate([]) == 0.0


def test_two_week_completion_rate_clears_target() -> None:
    """A 2-week scoped set with 8/10 completed clears the >60% target (axiom 09)."""
    two_weeks = [_ev(f"t{i}", completed=(i < 8)) for i in range(10)]
    assert metrics.completion_rate(two_weeks) == 0.8
    assert metrics.completion_rate(two_weeks) > 0.60


def test_median_duration_error_excludes_estimated_and_handles_empty() -> None:
    # ratios: 135/90 = 0.5 error; 90/90 = 0.0; 45/90 = 0.5  -> median 0.5
    events = [
        _ev("a", sched=90, actual=135),
        _ev("b", sched=90, actual=90),
        _ev("c", sched=90, actual=45),
        # an estimated event would be a fake 0.0 error — must be excluded
        _ev("d", sched=90, actual=90, estimated=True, dq=DataQuality.PARTIAL_ESTIMATED),
    ]
    assert metrics.median_duration_error(events) == 0.5
    # no measured completions -> None (undefined, not 0.0)
    assert metrics.median_duration_error([_ev("x", completed=False)]) is None


def test_schedule_edit_rate() -> None:
    events = [
        _ev("a", reschedule=0),
        _ev("b", reschedule=2),
        _ev("c", reschedule=1),
        _ev("d", reschedule=0),
    ]
    assert metrics.schedule_edit_rate(events) == 0.5


def test_completion_lift_is_signed_difference() -> None:
    baseline = [_ev(f"b{i}", completed=(i < 5)) for i in range(10)]  # 0.5
    current = [_ev(f"c{i}", completed=(i < 8)) for i in range(10)]  # 0.8
    assert metrics.completion_lift(baseline, current) == pytest.approx(0.3)


def test_acceptance_and_opt_in_rates_validate_inputs() -> None:
    assert metrics.acceptance_rate(offered=10, accepted=4) == 0.4
    assert metrics.acceptance_rate(offered=0, accepted=0) == 0.0
    assert metrics.opt_in_rate(eligible=20, opted_in=5) == 0.25
    with pytest.raises(ValueError):
        metrics.acceptance_rate(offered=2, accepted=3)
    with pytest.raises(ValueError):
        metrics.opt_in_rate(eligible=2, opted_in=3)


def test_metrics_report_aggregates() -> None:
    events = [
        _ev("a", sched=90, actual=135, reschedule=1),
        _ev("b", sched=60, actual=60),
        _ev("c", completed=False),
    ]
    report = metrics.MetricsReport.from_events(events)
    assert report.sample_size == 3
    assert report.completed_count == 2
    assert report.completion_rate == pytest.approx(2 / 3)
    assert report.median_duration_error == pytest.approx(0.25)  # median(0.5, 0.0)
    assert report.schedule_edit_rate == pytest.approx(1 / 3)
