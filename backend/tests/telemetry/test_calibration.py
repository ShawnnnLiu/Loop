"""Tests for deterministic duration calibration (Phase 4)."""

from __future__ import annotations

import statistics
from datetime import UTC, datetime

import pytest

from agentic_calendar.contracts.common_types import TaskCategory
from agentic_calendar.contracts.telemetry import DataQuality, TelemetryEvent
from agentic_calendar.telemetry.calibration import calibrate

TS = datetime(2026, 5, 12, tzinfo=UTC)


def _ev(
    tid: str,
    *,
    sched: int = 90,
    actual: int = 135,
    completed: bool = True,
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
        user_reschedule_count=0,
        data_quality=dq,
        duration_estimated=estimated,
    )


def _cats(n: int, category: TaskCategory, prefix: str = "t") -> dict[str, TaskCategory]:
    return {f"{prefix}{i}": category for i in range(n)}


def test_multiplier_is_clamped_weighted_median() -> None:
    # 5 PRACTICE completions, ratio 1.5 each -> median 1.5, within band
    events = [_ev(f"t{i}") for i in range(5)]
    udm = calibrate(events, _cats(5, TaskCategory.PRACTICE), user_id="u1", now=TS)
    m = udm.as_map()
    assert m[TaskCategory.PRACTICE] == 1.5
    entry = udm.multipliers[0]
    assert entry.observed_ratio == 1.5
    assert entry.sample_size == 5


def test_clamp_high_and_low() -> None:
    high = [_ev(f"h{i}", sched=60, actual=180) for i in range(5)]  # ratio 3.0
    udm_high = calibrate(high, _cats(5, TaskCategory.PROJECT, "h"), user_id="u", now=TS)
    assert udm_high.multipliers[0].multiplier == 2.0  # clamped to max
    assert udm_high.multipliers[0].observed_ratio == 3.0

    low = [_ev(f"l{i}", sched=100, actual=20) for i in range(5)]  # ratio 0.2
    udm_low = calibrate(low, _cats(5, TaskCategory.REVIEW, "l"), user_id="u", now=TS)
    assert udm_low.multipliers[0].multiplier == 0.5  # clamped to min


def test_estimated_events_are_excluded() -> None:
    # all five are estimated -> no real measurements -> category omitted
    events = [
        _ev(f"t{i}", estimated=True, dq=DataQuality.PARTIAL_ESTIMATED, actual=90)
        for i in range(5)
    ]
    udm = calibrate(events, _cats(5, TaskCategory.PRACTICE), user_id="u1", now=TS)
    assert udm.as_map() == {}


def test_insufficient_sample_omits_category() -> None:
    events = [_ev(f"t{i}") for i in range(4)]  # 4 < min_weighted_sample (5)
    udm = calibrate(events, _cats(4, TaskCategory.PRACTICE), user_id="u1", now=TS)
    assert udm.as_map() == {}


def test_manual_backfill_half_weight_gate() -> None:
    # 9 manual_backfill events -> weighted 4.5 < 5 -> omitted
    nine = [_ev(f"t{i}", dq=DataQuality.MANUAL_BACKFILL) for i in range(9)]
    udm9 = calibrate(nine, _cats(9, TaskCategory.PRACTICE), user_id="u", now=TS)
    assert udm9.as_map() == {}

    # 10 manual_backfill events -> weighted 5.0 >= 5 -> included
    ten = [_ev(f"t{i}", dq=DataQuality.MANUAL_BACKFILL) for i in range(10)]
    udm10 = calibrate(ten, _cats(10, TaskCategory.PRACTICE), user_id="u", now=TS)
    assert udm10.as_map() == {TaskCategory.PRACTICE: 1.5}
    assert udm10.multipliers[0].sample_size == 10


def test_unattributed_tasks_are_skipped() -> None:
    events = [_ev(f"t{i}") for i in range(5)]
    # only 4 of 5 task_ids are attributable -> 4 weighted < 5 -> omitted
    partial = {f"t{i}": TaskCategory.PRACTICE for i in range(4)}
    udm = calibrate(events, partial, user_id="u1", now=TS)
    assert udm.as_map() == {}


def test_calibration_is_deterministic() -> None:
    events = [_ev(f"t{i}", actual=120 + i) for i in range(6)]
    cats = _cats(6, TaskCategory.PRACTICE)
    a = calibrate(events, cats, user_id="u1", now=TS)
    b = calibrate(events, cats, user_id="u1", now=TS)
    assert a.model_dump() == b.model_dump()


def test_even_count_weighted_median_matches_statistics_median() -> None:
    """With equal weights the weighted median equals ``statistics.median`` —
    so calibration's correction agrees with the median the drift classifier
    uses to detect duration drift (no silent under/overshoot on even counts)."""
    actuals = [120, 121, 122, 123, 124, 125]  # 6 events -> even count
    events = [_ev(f"t{i}", sched=90, actual=a) for i, a in enumerate(actuals)]
    expected = statistics.median([a / 90 for a in actuals])  # avg of 2 middle
    udm = calibrate(events, _cats(6, TaskCategory.PRACTICE), user_id="u1", now=TS)
    entry = udm.multipliers[0]
    assert entry.observed_ratio == pytest.approx(expected)
    assert entry.multiplier == pytest.approx(expected)  # within clamp band
