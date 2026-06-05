"""``user_duration_multipliers`` contract.

Canonical reference: ``docs/axioms/17-duration-estimation.md`` (Phase 2
"Simple Per-User Calibration"), ``docs/axioms/07-telemetry-and-drift.md``.

:class:`UserDurationMultipliers` is the output of duration calibration
(``telemetry/calibration.py``) and the input to the deterministic duration
transform (``duration_estimation/``). It records, per :class:`TaskCategory`, a
multiplier learned from completed-task telemetry, alongside the sample size it
rests on so the value is auditable (uncalibrated/sparse categories are simply
absent — the transform treats a missing category as a 1.0 no-op).

This is deterministic configuration learned from telemetry, not an LLM artifact:
the LLM never assigns a multiplier.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .common_types import TaskCategory


class CategoryMultiplier(BaseModel):
    """A learned duration multiplier for one task category."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    category: TaskCategory
    multiplier: float = Field(gt=0.0)
    sample_size: int = Field(ge=0)
    observed_ratio: float = Field(gt=0.0)


class UserDurationMultipliers(BaseModel):
    """Per-user, per-category duration multipliers learned from telemetry."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    user_id: str = Field(min_length=1)
    computed_at: datetime
    multipliers: list[CategoryMultiplier] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique_categories(self) -> UserDurationMultipliers:
        seen: set[TaskCategory] = set()
        dupes: list[str] = []
        for m in self.multipliers:
            if m.category in seen:
                dupes.append(m.category.value)
            seen.add(m.category)
        if dupes:
            raise ValueError(f"duplicate category multipliers: {sorted(set(dupes))}")
        return self

    @model_validator(mode="after")
    def _computed_at_aware(self) -> UserDurationMultipliers:
        if self.computed_at.tzinfo is None:
            raise ValueError("computed_at must be timezone-aware")
        return self

    def as_map(self) -> dict[TaskCategory, float]:
        """Return ``{category: multiplier}`` for the duration transform.

        A category absent from the result means "no calibration" — the
        transform applies an implicit 1.0 (leaves the estimate unchanged).
        """
        return {m.category: m.multiplier for m in self.multipliers}
