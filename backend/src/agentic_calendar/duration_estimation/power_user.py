"""Power-user gate and per-user refinement (Phase 6c; ADR-0007).

The gate is a pure, replay-deterministic function over caller-supplied
aggregates: the composition root knows the schedule, so it supplies weekly
``(scheduled_count, completed_count)`` aggregates — telemetry alone cannot
attribute scheduled-but-missed work to weeks. Every criterion is evaluated
(no short-circuit) and logged with observed value, threshold, and — when
unmet — its own typed reason code, so eligibility is auditable like the
accountability policy engine.

Refinement trains only for eligible ``(user, category)`` pairs; ineligible
users keep Phase 6b behavior byte-identical. Statistics mirror Phase 2
calibration (weighted medians, sufficiency floor, clamp band) — never ML.

All thresholds are uncalibrated heuristic priors (axiom 07); 200 / 30 / 4
weeks come from axiom 17 Phase 4.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from statistics import pvariance
from zoneinfo import ZoneInfo

from agentic_calendar.contracts.common_types import TaskCategory
from agentic_calendar.contracts.pooled_duration_model import TimeOfDayBand
from agentic_calendar.contracts.power_user import (
    CRITERION_REASON_CODES,
    EligibilityCriterion,
    EligibilityCriterionEvaluation,
    PerUserRefinement,
    PowerUserEligibility,
    RefinementEntry,
)
from agentic_calendar.contracts.telemetry import DataQuality, TelemetryEvent

from .pooled import derive_time_of_day_band

#: Telemetry data-quality weights (telemetry spec), shared with calibration.
_QUALITY_WEIGHTS: dict[DataQuality, float] = {
    DataQuality.COMPLETE: 1.0,
    DataQuality.OFFLINE_SYNCED: 1.0,
    DataQuality.PARTIAL_ESTIMATED: 0.5,
    DataQuality.MANUAL_BACKFILL: 0.5,
}


@dataclass(frozen=True)
class WeeklyActivity:
    """One week's scheduling aggregate, supplied by the composition root."""

    scheduled_count: int
    completed_count: int


@dataclass(frozen=True)
class EligibilityConfig:
    """Gate thresholds (axiom 17 Phase 4 values; heuristic priors)."""

    min_total_completions: int = 200
    min_category_completions: int = 30
    min_assessable_weeks: int = 4
    min_weekly_scheduled: int = 3
    max_completion_rate_variance: float = 0.02


DEFAULT_ELIGIBILITY_CONFIG = EligibilityConfig()

#: The variance threshold is clamped to this band at evaluation time (spec).
_VARIANCE_THRESHOLD_BAND = (0.0, 0.25)


def evaluate_power_user_eligibility(
    user_id: str,
    category: TaskCategory,
    *,
    total_completed_tasks: int,
    category_completed_tasks: int,
    weekly_activity: Sequence[WeeklyActivity],
    evaluated_at: datetime,
    config: EligibilityConfig = DEFAULT_ELIGIBILITY_CONFIG,
) -> PowerUserEligibility:
    """Evaluate the four-criterion gate for one ``(user, category)``.

    Deterministic and fully logged: all four criteria are always evaluated.
    With fewer than two assessable weeks the stability variance is defined
    as 0.0 — the ``assessable_weeks`` criterion reports the sufficiency
    problem; a single observation carries no instability evidence (spec).
    """
    assessable_rates = [
        w.completed_count / w.scheduled_count
        for w in weekly_activity
        if w.scheduled_count >= config.min_weekly_scheduled
    ]
    variance = pvariance(assessable_rates) if len(assessable_rates) >= 2 else 0.0
    variance_threshold = min(
        max(config.max_completion_rate_variance, _VARIANCE_THRESHOLD_BAND[0]),
        _VARIANCE_THRESHOLD_BAND[1],
    )

    checks: list[tuple[EligibilityCriterion, float, float, bool]] = [
        (
            EligibilityCriterion.TOTAL_COMPLETIONS,
            float(total_completed_tasks),
            float(config.min_total_completions),
            total_completed_tasks >= config.min_total_completions,
        ),
        (
            EligibilityCriterion.CATEGORY_COMPLETIONS,
            float(category_completed_tasks),
            float(config.min_category_completions),
            category_completed_tasks >= config.min_category_completions,
        ),
        (
            EligibilityCriterion.ASSESSABLE_WEEKS,
            float(len(assessable_rates)),
            float(config.min_assessable_weeks),
            len(assessable_rates) >= config.min_assessable_weeks,
        ),
        (
            EligibilityCriterion.COMPLETION_RATE_STABILITY,
            variance,
            variance_threshold,
            variance <= variance_threshold,  # inclusive boundary (spec)
        ),
    ]
    criteria = [
        EligibilityCriterionEvaluation(
            criterion=criterion,
            observed_value=observed,
            threshold_value=threshold,
            met=met,
            reason_code=None if met else CRITERION_REASON_CODES[criterion],
        )
        for criterion, observed, threshold, met in checks
    ]
    return PowerUserEligibility(
        user_id=user_id,
        category=category,
        evaluated_at=evaluated_at,
        eligible=all(c.met for c in criteria),
        criteria=criteria,
    )


@dataclass(frozen=True)
class RefinementConfig:
    """Refinement training parameters (heuristic priors; Phase 2 bands)."""

    min_weighted_sample: float = 5.0
    multiplier_min: float = 0.5
    multiplier_max: float = 2.0


DEFAULT_REFINEMENT_CONFIG = RefinementConfig()


def _weighted_median(pairs: Sequence[tuple[float, float]]) -> float:
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


def train_per_user_refinement(
    events: Sequence[TelemetryEvent],
    task_categories: Mapping[str, TaskCategory],
    *,
    user_id: str,
    timezone: str,
    eligibilities: Sequence[PowerUserEligibility],
    computed_at: datetime,
    config: RefinementConfig = DEFAULT_REFINEMENT_CONFIG,
) -> PerUserRefinement:
    """Train ``(category x time-of-day band)`` multipliers behind the gate.

    Only categories whose eligibility object is ``eligible`` produce
    entries; everything else is skipped, so an ineligible user's refinement
    is empty and serving falls through to Phase 6b unchanged. ``events``
    must already be scoped to ``user_id`` by the caller.
    """
    eligible_categories = {e.category for e in eligibilities if e.eligible}
    tz = ZoneInfo(timezone)
    by_key: dict[tuple[str, str], list[tuple[float, float]]] = {}
    counts: dict[tuple[str, str], int] = {}

    for event in events:
        if not event.completed or event.duration_estimated:
            continue
        if event.actual_duration_min is None or event.scheduled_duration_min <= 0:
            continue
        if event.completion_timestamp is None:
            continue
        category = task_categories.get(event.task_id)
        if category is None or category not in eligible_categories:
            continue
        weight = _QUALITY_WEIGHTS.get(event.data_quality, 0.0)
        if weight <= 0.0:
            continue
        band = derive_time_of_day_band(event.completion_timestamp.astimezone(tz).hour)
        key = (category.value, band.value)
        ratio = event.actual_duration_min / event.scheduled_duration_min
        by_key.setdefault(key, []).append((ratio, weight))
        counts[key] = counts.get(key, 0) + 1

    entries: list[RefinementEntry] = []
    for key in sorted(by_key):
        pairs = by_key[key]
        weighted_sample = sum(w for _, w in pairs)
        if weighted_sample < config.min_weighted_sample:
            continue
        observed = _weighted_median(pairs)
        entries.append(
            RefinementEntry(
                category=TaskCategory(key[0]),
                time_of_day_band=TimeOfDayBand(key[1]),
                multiplier=max(
                    config.multiplier_min, min(config.multiplier_max, observed)
                ),
                sample_size=counts[key],
                weighted_sample=weighted_sample,
                observed_ratio=observed,
            )
        )
    return PerUserRefinement(user_id=user_id, computed_at=computed_at, entries=entries)
