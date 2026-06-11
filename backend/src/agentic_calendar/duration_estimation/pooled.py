"""Pooled-duration training and serving (Phase 6b; ADR-0007).

Training is a **pure function** over caller-supplied inputs: the composition
root passes telemetry events, per-task attributes, per-user context, and the
consented user-id set in from outside the region set (this kernel imports
neither ``telemetry/`` nor ``consent/``). Only consented users' events enter
any statistic; rebuilding from the same inputs yields the same
``content_hash`` (replay determinism).

Serving resolves one effective multiplier per task category through the
spec'd deterministic fallback chain — pooled bucket → per-user category
multiplier (Phase 2 calibration) → heuristic baseline (1.0) — recording a
typed reason code for every skipped tier and naming the source that won.
Pooled absence, sparsity, invalidity, or consent denial never blocks
planning.

All thresholds here (shrinkage strength, serving floor, clamp band, band
boundaries) are uncalibrated heuristic priors (axiom 07 threshold honesty).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from zoneinfo import ZoneInfo

from agentic_calendar.contracts.common_types import ExperienceLevel, TaskCategory
from agentic_calendar.contracts.hashing import canonical_mapping_hash
from agentic_calendar.contracts.pooled_duration_model import (
    CompletionRateBand,
    DayOfWeek,
    MultiplierBand,
    PooledBucket,
    PooledDurationModel,
    TimeOfDayBand,
)
from agentic_calendar.contracts.reason_codes import ReasonCode
from agentic_calendar.contracts.telemetry import DataQuality, TelemetryEvent
from agentic_calendar.contracts.user_duration_multipliers import (
    CategoryMultiplier,
    UserDurationMultipliers,
)

FEATURE_SCHEMA_VERSION = "1"

#: Telemetry data-quality weights (telemetry spec), mirroring Phase 2
#: calibration so the two estimators agree on evidence trust.
_QUALITY_WEIGHTS: dict[DataQuality, float] = {
    DataQuality.COMPLETE: 1.0,
    DataQuality.OFFLINE_SYNCED: 1.0,
    DataQuality.PARTIAL_ESTIMATED: 0.5,
    DataQuality.MANUAL_BACKFILL: 0.5,
}


def derive_time_of_day_band(local_hour: int) -> TimeOfDayBand:
    """Map a local hour (0-23) to its band (spec feature table)."""
    if 5 <= local_hour <= 11:
        return TimeOfDayBand.MORNING
    if 12 <= local_hour <= 16:
        return TimeOfDayBand.AFTERNOON
    if 17 <= local_hour <= 21:
        return TimeOfDayBand.EVENING
    return TimeOfDayBand.NIGHT


_DAYS = (
    DayOfWeek.MON,
    DayOfWeek.TUE,
    DayOfWeek.WED,
    DayOfWeek.THU,
    DayOfWeek.FRI,
    DayOfWeek.SAT,
    DayOfWeek.SUN,
)


def derive_completion_rate_band(rate: float) -> CompletionRateBand:
    """Band boundaries 0.5 / 0.8 (heuristic priors)."""
    if rate < 0.5:
        return CompletionRateBand.LOW
    if rate < 0.8:
        return CompletionRateBand.MEDIUM
    return CompletionRateBand.HIGH


def derive_multiplier_band(multiplier: float) -> MultiplierBand:
    """Band boundaries 0.9 / 1.1 (heuristic priors); 1.0 when uncalibrated."""
    if multiplier < 0.9:
        return MultiplierBand.FASTER
    if multiplier <= 1.1:
        return MultiplierBand.BASELINE
    return MultiplierBand.SLOWER


@dataclass(frozen=True)
class PooledTrainingInput:
    """One user's training slice, assembled by the composition root.

    ``task_categories``/``task_cognitive_loads`` map ``task_id`` to the task
    attributes (events whose task is absent are skipped — unattributable).
    ``recent_completion_rate`` is the caller-computed rate in ``[0, 1]``;
    ``historical_multipliers`` is the user's Phase 2 calibration (or None).
    ``timezone`` is the IANA zone used to localize completion timestamps.
    """

    user_id: str
    events: Sequence[TelemetryEvent]
    task_categories: Mapping[str, TaskCategory]
    task_cognitive_loads: Mapping[str, int]
    experience_level: ExperienceLevel
    timezone: str
    recent_completion_rate: float
    historical_multipliers: UserDurationMultipliers | None = None


@dataclass(frozen=True)
class PooledTrainingConfig:
    """Tunable, deterministic training parameters (heuristic priors)."""

    shrinkage_strength: float = 5.0
    multiplier_min: float = 0.5
    multiplier_max: float = 2.0


DEFAULT_POOLED_TRAINING_CONFIG = PooledTrainingConfig()


def _weighted_median(pairs: Sequence[tuple[float, float]]) -> float:
    """Weighted median of ``(value, weight)`` pairs; same semantics as the
    Phase 2 calibration median (see ``telemetry/calibration.py``)."""
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


_FeatureKey = tuple[str, int, str, str, str, str, str]


def train_pooled_model(
    inputs: Sequence[PooledTrainingInput],
    *,
    consented_user_ids: set[str],
    model_version: str,
    trained_at: datetime,
    config: PooledTrainingConfig = DEFAULT_POOLED_TRAINING_CONFIG,
) -> PooledDurationModel:
    """Build the pooled artifact from consented users' telemetry.

    Pure and replay-deterministic: the same inputs produce a byte-identical
    artifact with the same ``content_hash``. Inputs for users outside
    ``consented_user_ids`` are skipped entirely — they contribute to no
    bucket and not to the global prior (the opt-out-removes-from-training
    guarantee; the composition root additionally audits each user's gate
    check).
    """
    all_pairs: list[tuple[float, float]] = []
    by_key: dict[_FeatureKey, list[tuple[float, float]]] = {}
    counts: dict[_FeatureKey, int] = {}

    for user_input in inputs:
        if user_input.user_id not in consented_user_ids:
            continue
        tz = ZoneInfo(user_input.timezone)
        completion_band = derive_completion_rate_band(user_input.recent_completion_rate)
        historical = (
            user_input.historical_multipliers.as_map()
            if user_input.historical_multipliers is not None
            else {}
        )
        for event in user_input.events:
            if not event.completed or event.duration_estimated:
                continue
            if event.actual_duration_min is None or event.scheduled_duration_min <= 0:
                continue
            if event.completion_timestamp is None:
                continue
            category = user_input.task_categories.get(event.task_id)
            cognitive_load = user_input.task_cognitive_loads.get(event.task_id)
            if category is None or cognitive_load is None:
                continue
            weight = _QUALITY_WEIGHTS.get(event.data_quality, 0.0)
            if weight <= 0.0:
                continue
            local = event.completion_timestamp.astimezone(tz)
            key: _FeatureKey = (
                category.value,
                cognitive_load,
                user_input.experience_level.value,
                derive_time_of_day_band(local.hour).value,
                _DAYS[local.weekday()].value,
                completion_band.value,
                derive_multiplier_band(historical.get(category, 1.0)).value,
            )
            ratio = event.actual_duration_min / event.scheduled_duration_min
            all_pairs.append((ratio, weight))
            by_key.setdefault(key, []).append((ratio, weight))
            counts[key] = counts.get(key, 0) + 1

    if all_pairs:
        prior = _clamp(
            _weighted_median(all_pairs), config.multiplier_min, config.multiplier_max
        )
        prior_sample = sum(w for _, w in all_pairs)
    else:
        prior = 1.0
        prior_sample = 0.0

    buckets: list[PooledBucket] = []
    for key in sorted(by_key):
        pairs = by_key[key]
        weighted_sample = sum(w for _, w in pairs)
        observed = _weighted_median(pairs)
        shrunk = (weighted_sample * observed + config.shrinkage_strength * prior) / (
            weighted_sample + config.shrinkage_strength
        )
        buckets.append(
            PooledBucket(
                category=TaskCategory(key[0]),
                cognitive_load=key[1],
                experience_level=ExperienceLevel(key[2]),
                time_of_day_band=TimeOfDayBand(key[3]),
                day_of_week=DayOfWeek(key[4]),
                completion_rate_band=CompletionRateBand(key[5]),
                multiplier_band=MultiplierBand(key[6]),
                multiplier=_clamp(shrunk, config.multiplier_min, config.multiplier_max),
                sample_size=counts[key],
                weighted_sample=weighted_sample,
                observed_ratio=observed,
            )
        )

    hashed_payload = {
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "global_prior_multiplier": prior,
        "global_prior_weighted_sample": prior_sample,
        "shrinkage_strength": config.shrinkage_strength,
        "multiplier_min": config.multiplier_min,
        "multiplier_max": config.multiplier_max,
        "buckets": [b.hashed_payload() for b in buckets],
    }
    return PooledDurationModel(
        model_version=model_version,
        feature_schema_version=FEATURE_SCHEMA_VERSION,
        trained_at=trained_at,
        global_prior_multiplier=prior,
        global_prior_weighted_sample=prior_sample,
        shrinkage_strength=config.shrinkage_strength,
        multiplier_min=config.multiplier_min,
        multiplier_max=config.multiplier_max,
        buckets=buckets,
        content_hash=canonical_mapping_hash(hashed_payload),
    )


# --------------------------------------------------------------------------
# Serving
# --------------------------------------------------------------------------


class DurationSource(StrEnum):
    """Which tier of the fallback chain produced the multiplier."""

    POOLED = "pooled"
    PER_USER_CATEGORY = "per_user_category"
    HEURISTIC_BASELINE = "heuristic_baseline"


@dataclass(frozen=True)
class DurationResolution:
    """One category's resolved multiplier, fully explainable.

    ``fallback_reasons`` records the typed reason for every tier skipped
    before ``source`` won; ``debug`` carries the query and match statistics
    (spec: the debug payload names which source won).
    """

    category: TaskCategory
    multiplier: float
    source: DurationSource
    fallback_reasons: tuple[ReasonCode, ...]
    debug: dict[str, object]


@dataclass(frozen=True)
class PooledServingConfig:
    """Serving floor for the pooled tier (heuristic prior)."""

    serving_floor: float = 5.0


DEFAULT_POOLED_SERVING_CONFIG = PooledServingConfig()


def resolve_duration_multiplier(
    category: TaskCategory,
    *,
    experience_level: ExperienceLevel,
    recent_completion_rate: float,
    per_user: UserDurationMultipliers | None,
    model: PooledDurationModel | None,
    pooled_denial_reason: ReasonCode | None = None,
    config: PooledServingConfig = DEFAULT_POOLED_SERVING_CONFIG,
) -> DurationResolution:
    """Resolve one category's effective multiplier via the fallback chain.

    ``pooled_denial_reason`` is the consent gate's denial code for the
    ``pooled_serving`` purpose (``CONSENT_MISSING``/``CONSENT_REVOKED``), or
    None when the gate allowed; the gate check (and its audit entry) belongs
    to the composition root. ``model`` is None when no artifact exists or it
    failed contract validation (``POOLED_MODEL_UNAVAILABLE``).

    At replan time the scheduled slot and per-task load are unknown, so the
    pooled query marginalizes over ``cognitive_load``, ``time_of_day_band``,
    and ``day_of_week`` (spec "Serving And Fallback Chain").
    """
    per_user_map = per_user.as_map() if per_user is not None else {}
    historical = per_user_map.get(category, 1.0)
    completion_band = derive_completion_rate_band(recent_completion_rate)
    multiplier_band = derive_multiplier_band(historical)
    debug: dict[str, object] = {
        "query": {
            "category": category.value,
            "experience_level": experience_level.value,
            "completion_rate_band": completion_band.value,
            "multiplier_band": multiplier_band.value,
        },
        "serving_floor": config.serving_floor,
        "matched_bucket_count": 0,
        "combined_weighted_sample": 0.0,
    }
    fallback_reasons: list[ReasonCode] = []

    pooled_skip: ReasonCode | None
    if pooled_denial_reason is not None:
        pooled_skip = pooled_denial_reason
    elif model is None:
        pooled_skip = ReasonCode.POOLED_MODEL_UNAVAILABLE
    else:
        matches = [
            b
            for b in model.buckets
            if b.category is category
            and b.experience_level is experience_level
            and b.completion_rate_band is completion_band
            and b.multiplier_band is multiplier_band
        ]
        combined = sum(b.weighted_sample for b in matches)
        debug["matched_bucket_count"] = len(matches)
        debug["combined_weighted_sample"] = combined
        debug["combined_sample_size"] = sum(b.sample_size for b in matches)
        if not matches or combined < config.serving_floor:
            pooled_skip = ReasonCode.POOLED_BUCKET_SPARSE
        else:
            if len(matches) == 1:
                # No aggregation needed; avoids float drift vs the bucket value.
                pooled = matches[0].multiplier
            else:
                pooled = sum(b.multiplier * b.weighted_sample for b in matches) / combined
            pooled = _clamp(pooled, model.multiplier_min, model.multiplier_max)
            debug["source"] = DurationSource.POOLED.value
            return DurationResolution(
                category=category,
                multiplier=pooled,
                source=DurationSource.POOLED,
                fallback_reasons=(),
                debug=debug,
            )
    fallback_reasons.append(pooled_skip)

    if category in per_user_map:
        debug["source"] = DurationSource.PER_USER_CATEGORY.value
        return DurationResolution(
            category=category,
            multiplier=per_user_map[category],
            source=DurationSource.PER_USER_CATEGORY,
            fallback_reasons=tuple(fallback_reasons),
            debug=debug,
        )

    debug["source"] = DurationSource.HEURISTIC_BASELINE.value
    return DurationResolution(
        category=category,
        multiplier=1.0,
        source=DurationSource.HEURISTIC_BASELINE,
        fallback_reasons=tuple(fallback_reasons),
        debug=debug,
    )


def resolve_effective_multipliers(
    categories: Sequence[TaskCategory],
    *,
    user_id: str,
    computed_at: datetime,
    experience_level: ExperienceLevel,
    recent_completion_rate: float,
    per_user: UserDurationMultipliers | None,
    model: PooledDurationModel | None,
    pooled_denial_reason: ReasonCode | None = None,
    config: PooledServingConfig = DEFAULT_POOLED_SERVING_CONFIG,
) -> tuple[UserDurationMultipliers, list[DurationResolution]]:
    """Resolve every category once and package the result for the transform.

    The returned :class:`UserDurationMultipliers` feeds the existing
    ``apply_duration_calibration`` unchanged, so plan application stays on
    the replan path (new draft plan version; the active plan is never
    mutated). Baseline (1.0) resolutions are omitted from the multiplier set
    — the transform treats a missing category as a 1.0 no-op — but every
    resolution is returned for the debug/audit surface.
    """
    resolutions: list[DurationResolution] = []
    multipliers: list[CategoryMultiplier] = []
    for category in sorted(set(categories), key=lambda c: c.value):
        resolution = resolve_duration_multiplier(
            category,
            experience_level=experience_level,
            recent_completion_rate=recent_completion_rate,
            per_user=per_user,
            model=model,
            pooled_denial_reason=pooled_denial_reason,
            config=config,
        )
        resolutions.append(resolution)
        if resolution.source is DurationSource.HEURISTIC_BASELINE:
            continue
        if resolution.source is DurationSource.PER_USER_CATEGORY and per_user is not None:
            # Carry the Phase 2 entry through verbatim — its sample size and
            # observed ratio are the audit trail for this value.
            original = next(m for m in per_user.multipliers if m.category is category)
            multipliers.append(original)
            continue
        combined_sample = resolution.debug.get("combined_sample_size", 0)
        multipliers.append(
            CategoryMultiplier(
                category=category,
                multiplier=resolution.multiplier,
                sample_size=combined_sample if isinstance(combined_sample, int) else 0,
                # Post-aggregation the per-bucket observed ratios are already
                # blended; the effective multiplier is the auditable value.
                observed_ratio=resolution.multiplier,
            )
        )
    return (
        UserDurationMultipliers(
            user_id=user_id, computed_at=computed_at, multipliers=multipliers
        ),
        resolutions,
    )
