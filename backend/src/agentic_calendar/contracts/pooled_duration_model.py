"""``pooled_duration_model`` contract.

Canonical spec: ``docs/specs/pooled-duration-model.schema.md``.

:class:`PooledDurationModel` is the versioned, deterministic artifact produced
by pooled-duration training (axiom 17 Phase 3; ADR-0007). It is **not an ML
model**: feature-bucketed pooled multipliers with sample-size shrinkage toward
a global prior, rebuildable byte-identically from the same inputs. The
artifact contains no user identifiers — only feature buckets and aggregate
statistics.

The ``content_hash`` is recomputed by the validator over the canonical hashed
payload (everything except ``model_version`` and ``trained_at``); a tampered
or corrupted artifact fails validation, and the serving chain treats it as
``POOLED_MODEL_UNAVAILABLE``.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .common_types import ExperienceLevel, TaskCategory
from .hashing import canonical_mapping_hash


class TimeOfDayBand(StrEnum):
    """Local-time band of the completion timestamp (spec feature table)."""

    MORNING = "morning"  # 05:00-11:59
    AFTERNOON = "afternoon"  # 12:00-16:59
    EVENING = "evening"  # 17:00-21:59
    NIGHT = "night"  # 22:00-04:59


class DayOfWeek(StrEnum):
    MON = "mon"
    TUE = "tue"
    WED = "wed"
    THU = "thu"
    FRI = "fri"
    SAT = "sat"
    SUN = "sun"


class CompletionRateBand(StrEnum):
    """Recent-completion-rate band; boundaries are heuristic priors."""

    LOW = "low"  # rate < 0.5
    MEDIUM = "medium"  # 0.5 <= rate < 0.8
    HIGH = "high"  # rate >= 0.8


class MultiplierBand(StrEnum):
    """Historical per-category multiplier band; boundaries are heuristic priors."""

    FASTER = "faster"  # m < 0.9
    BASELINE = "baseline"  # 0.9 <= m <= 1.1
    SLOWER = "slower"  # m > 1.1


class PooledBucket(BaseModel):
    """Aggregate statistics for one observed feature tuple."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    category: TaskCategory
    cognitive_load: int = Field(ge=1, le=5)
    experience_level: ExperienceLevel
    time_of_day_band: TimeOfDayBand
    day_of_week: DayOfWeek
    completion_rate_band: CompletionRateBand
    multiplier_band: MultiplierBand
    multiplier: float = Field(gt=0.0)
    sample_size: int = Field(ge=1)
    weighted_sample: float = Field(gt=0.0)
    observed_ratio: float = Field(gt=0.0)

    def feature_key(self) -> tuple[str, int, str, str, str, str, str]:
        """Canonical sort/uniqueness key over the seven feature dimensions."""
        return (
            self.category.value,
            self.cognitive_load,
            self.experience_level.value,
            self.time_of_day_band.value,
            self.day_of_week.value,
            self.completion_rate_band.value,
            self.multiplier_band.value,
        )

    def hashed_payload(self) -> dict[str, Any]:
        """The bucket's contribution to the artifact ``content_hash``."""
        return {
            "category": self.category.value,
            "cognitive_load": self.cognitive_load,
            "experience_level": self.experience_level.value,
            "time_of_day_band": self.time_of_day_band.value,
            "day_of_week": self.day_of_week.value,
            "completion_rate_band": self.completion_rate_band.value,
            "multiplier_band": self.multiplier_band.value,
            "multiplier": self.multiplier,
            "sample_size": self.sample_size,
            "weighted_sample": self.weighted_sample,
            "observed_ratio": self.observed_ratio,
        }


class PooledDurationModel(BaseModel):
    """Versioned deterministic pooled-duration artifact (axiom 17 Phase 3)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    model_version: str = Field(min_length=1)
    feature_schema_version: str = Field(min_length=1)
    trained_at: datetime
    global_prior_multiplier: float = Field(gt=0.0)
    global_prior_weighted_sample: float = Field(ge=0.0)
    shrinkage_strength: float = Field(ge=0.0)
    multiplier_min: float = Field(gt=0.0)
    multiplier_max: float = Field(gt=0.0)
    buckets: list[PooledBucket] = Field(default_factory=list)
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    def hashed_payload(self) -> dict[str, Any]:
        """The canonical payload ``content_hash`` covers.

        ``model_version`` and ``trained_at`` are excluded on purpose: two
        builds of the same data under different labels/clocks share a hash,
        which is what makes the hash a replay proof of *data* equivalence.
        """
        return {
            "feature_schema_version": self.feature_schema_version,
            "global_prior_multiplier": self.global_prior_multiplier,
            "global_prior_weighted_sample": self.global_prior_weighted_sample,
            "shrinkage_strength": self.shrinkage_strength,
            "multiplier_min": self.multiplier_min,
            "multiplier_max": self.multiplier_max,
            "buckets": [b.hashed_payload() for b in self.buckets],
        }

    @model_validator(mode="after")
    def _trained_at_aware(self) -> PooledDurationModel:
        if self.trained_at.tzinfo is None:
            raise ValueError("trained_at must be timezone-aware")
        return self

    @model_validator(mode="after")
    def _clamp_band_ordered(self) -> PooledDurationModel:
        if self.multiplier_max < self.multiplier_min:
            raise ValueError("multiplier_max must be >= multiplier_min")
        return self

    @model_validator(mode="after")
    def _values_within_clamp_band(self) -> PooledDurationModel:
        if not (self.multiplier_min <= self.global_prior_multiplier <= self.multiplier_max):
            raise ValueError("global prior outside the artifact's clamp band")
        for bucket in self.buckets:
            if not (self.multiplier_min <= bucket.multiplier <= self.multiplier_max):
                raise ValueError("bucket multiplier outside the artifact's clamp band")
        return self

    @model_validator(mode="after")
    def _buckets_unique_and_canonically_ordered(self) -> PooledDurationModel:
        keys = [b.feature_key() for b in self.buckets]
        if len(set(keys)) != len(keys):
            raise ValueError("duplicate bucket feature tuples")
        if keys != sorted(keys):
            raise ValueError("buckets must be in canonical sorted order")
        return self

    @model_validator(mode="after")
    def _content_hash_matches(self) -> PooledDurationModel:
        expected = canonical_mapping_hash(self.hashed_payload())
        if self.content_hash != expected:
            raise ValueError("content_hash does not match the recomputed canonical hash")
        return self
