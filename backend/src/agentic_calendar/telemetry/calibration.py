"""Deterministic duration calibration (Phase 4).

Learns a per-:class:`TaskCategory` duration multiplier from completed-task
telemetry (axiom 17 "Simple Per-User Calibration"). The output
(:class:`UserDurationMultipliers`) feeds the ``duration_estimation`` transform,
which scales future estimates before validation/scheduling.

Design choices, all deterministic and documented as heuristic priors (pending
real calibration per axiom 07):

* **Only real measurements count.** ``duration_estimated`` events are excluded —
  their actual was defaulted to the scheduled value (ratio ≡ 1.0) and would drag
  every multiplier toward 1.0.
* **Trust weighting.** ``manual_backfill`` and ``partial_estimated`` events
  count at 0.5; ``complete`` and ``offline_synced`` at 1.0 (telemetry spec).
  Weights gate sufficiency and drive the weighted median.
* **Robust central tendency.** The multiplier is the *weighted median* of the
  ``actual / scheduled`` ratios, clamped to a sane band so sparse or outlier
  data cannot produce a runaway estimate. With equal evidence weights the
  weighted median equals ``statistics.median`` — the same median the drift
  classifier uses to *detect* duration drift — so detection and correction
  agree; low-trust events shift it only when their weights differ.
* **Sufficiency gate.** A category needs ``>= min_weighted_sample`` of weighted
  evidence or it is omitted entirely (the transform then leaves it at 1.0).

The LLM never assigns a multiplier; this is pure arithmetic over telemetry.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime

from agentic_calendar.contracts.common_types import TaskCategory
from agentic_calendar.contracts.telemetry import DataQuality, TelemetryEvent
from agentic_calendar.contracts.user_duration_multipliers import (
    CategoryMultiplier,
    UserDurationMultipliers,
)


def _default_quality_weights() -> dict[DataQuality, float]:
    return {
        DataQuality.COMPLETE: 1.0,
        DataQuality.OFFLINE_SYNCED: 1.0,
        DataQuality.PARTIAL_ESTIMATED: 0.5,
        DataQuality.MANUAL_BACKFILL: 0.5,
    }


@dataclass(frozen=True)
class CalibrationConfig:
    """Tunable, deterministic calibration parameters (heuristic priors)."""

    min_weighted_sample: float = 5.0
    multiplier_min: float = 0.5
    multiplier_max: float = 2.0
    quality_weights: Mapping[DataQuality, float] = field(
        default_factory=_default_quality_weights
    )


DEFAULT_CALIBRATION_CONFIG = CalibrationConfig()


def _weighted_median(pairs: Sequence[tuple[float, float]]) -> float:
    """Weighted median of ``(value, weight)`` pairs (weights > 0).

    Walks values in ascending order accumulating weight. When the cumulative
    weight *passes* half the total, that value is the median. When it lands
    *exactly* on half (an even split — e.g. equal weights over an even count),
    the median is the average of that value and the next, matching
    ``statistics.median``. This keeps calibration equal to the unweighted median
    the drift classifier uses whenever evidence weights are equal, while still
    down-weighting low-trust events when they are not.

    The exact-equality branch is float-safe here: weights are always 0.5 or 1.0
    (telemetry-spec data-quality weights), so partial sums are exact multiples
    of 0.5 and ``acc == half`` is reliable.
    """
    ordered = sorted(pairs, key=lambda p: p[0])
    total = sum(w for _, w in ordered)
    half = total / 2.0
    acc = 0.0
    for i, (value, weight) in enumerate(ordered):
        acc += weight
        if acc > half:
            return value
        if acc == half:
            nxt = ordered[i + 1][0] if i + 1 < len(ordered) else value
            return (value + nxt) / 2.0
    return ordered[-1][0]


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def calibrate(
    events: Sequence[TelemetryEvent],
    task_categories: Mapping[str, TaskCategory],
    *,
    user_id: str,
    now: datetime,
    config: CalibrationConfig = DEFAULT_CALIBRATION_CONFIG,
) -> UserDurationMultipliers:
    """Compute per-category duration multipliers from ``events``.

    ``events`` must already be scoped to ``user_id`` by the caller.
    ``task_categories`` maps ``task_id`` → :class:`TaskCategory`; events whose
    task is absent from the map are skipped (the category cannot be attributed).
    Categories with insufficient weighted evidence are omitted.
    """
    by_category: dict[TaskCategory, list[tuple[float, float]]] = {}

    for event in events:
        if not event.completed or event.duration_estimated:
            continue
        if event.actual_duration_min is None or event.scheduled_duration_min <= 0:
            continue
        category = task_categories.get(event.task_id)
        if category is None:
            continue
        ratio = event.actual_duration_min / event.scheduled_duration_min
        weight = config.quality_weights.get(event.data_quality, 0.0)
        if weight <= 0.0:
            continue
        by_category.setdefault(category, []).append((ratio, weight))

    multipliers: list[CategoryMultiplier] = []
    for category in sorted(by_category, key=lambda c: c.value):
        pairs = by_category[category]
        weighted_total = sum(w for _, w in pairs)
        if weighted_total < config.min_weighted_sample:
            continue
        observed_ratio = _weighted_median(pairs)
        multiplier = _clamp(
            observed_ratio, config.multiplier_min, config.multiplier_max
        )
        multipliers.append(
            CategoryMultiplier(
                category=category,
                multiplier=multiplier,
                sample_size=len(pairs),
                observed_ratio=observed_ratio,
            )
        )

    return UserDurationMultipliers(
        user_id=user_id,
        computed_at=now,
        multipliers=multipliers,
    )
