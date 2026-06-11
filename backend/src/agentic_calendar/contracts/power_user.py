"""``power_user_eligibility`` / ``per_user_refinement`` contracts.

Canonical spec: ``docs/specs/power-user-eligibility.schema.md``.

:class:`PowerUserEligibility` is the auditable gate decision for axiom 17
Phase 4: finer per-user multipliers train only for power users. Every
criterion is evaluated and logged with its observed value and threshold
(the ``PolicyRuleEvaluation`` pattern), and every unmet criterion carries
its own typed reason code.

:class:`PerUserRefinement` is the deterministic per-(category x
time-of-day-band) multiplier set trained only behind the gate — weighted
medians, never ML (ADR-0004 stays in force).
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .common_types import TaskCategory
from .pooled_duration_model import TimeOfDayBand
from .reason_codes import ReasonCode


class EligibilityCriterion(StrEnum):
    """The four gate criteria (spec "Eligibility Criteria")."""

    TOTAL_COMPLETIONS = "total_completions"
    CATEGORY_COMPLETIONS = "category_completions"
    ASSESSABLE_WEEKS = "assessable_weeks"
    COMPLETION_RATE_STABILITY = "completion_rate_stability"


#: The reason code an *unmet* criterion must carry (1:1, spec table).
CRITERION_REASON_CODES: dict[EligibilityCriterion, ReasonCode] = {
    EligibilityCriterion.TOTAL_COMPLETIONS: (
        ReasonCode.POWER_USER_TOTAL_COMPLETIONS_BELOW_THRESHOLD
    ),
    EligibilityCriterion.CATEGORY_COMPLETIONS: (
        ReasonCode.POWER_USER_CATEGORY_COMPLETIONS_BELOW_THRESHOLD
    ),
    EligibilityCriterion.ASSESSABLE_WEEKS: (
        ReasonCode.POWER_USER_INSUFFICIENT_ASSESSABLE_WEEKS
    ),
    EligibilityCriterion.COMPLETION_RATE_STABILITY: (
        ReasonCode.POWER_USER_COMPLETION_RATE_UNSTABLE
    ),
}


class EligibilityCriterionEvaluation(BaseModel):
    """Audit record of one criterion check (PolicyRuleEvaluation pattern)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    criterion: EligibilityCriterion
    observed_value: float
    threshold_value: float
    met: bool
    reason_code: ReasonCode | None = None

    @model_validator(mode="after")
    def _reason_code_matches_outcome(self) -> EligibilityCriterionEvaluation:
        expected = CRITERION_REASON_CODES[self.criterion]
        if self.met and self.reason_code is not None:
            raise ValueError("a met criterion must carry a null reason_code")
        if not self.met and self.reason_code is not expected:
            raise ValueError(
                f"unmet criterion '{self.criterion.value}' must carry "
                f"reason_code {expected.value}"
            )
        return self


class PowerUserEligibility(BaseModel):
    """The auditable power-user gate decision for one ``(user, category)``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    user_id: str = Field(min_length=1)
    category: TaskCategory
    evaluated_at: datetime
    eligible: bool
    criteria: list[EligibilityCriterionEvaluation]

    @model_validator(mode="after")
    def _evaluated_at_aware(self) -> PowerUserEligibility:
        if self.evaluated_at.tzinfo is None:
            raise ValueError("evaluated_at must be timezone-aware")
        return self

    @model_validator(mode="after")
    def _exactly_the_four_criteria(self) -> PowerUserEligibility:
        seen = [c.criterion for c in self.criteria]
        if sorted(c.value for c in seen) != sorted(c.value for c in EligibilityCriterion):
            raise ValueError("criteria must contain each of the four criteria exactly once")
        return self

    @model_validator(mode="after")
    def _eligible_is_conjunction(self) -> PowerUserEligibility:
        if self.eligible != all(c.met for c in self.criteria):
            raise ValueError("eligible must equal the conjunction of the criteria")
        return self

    def unmet_reason_codes(self) -> tuple[ReasonCode, ...]:
        """Typed reasons for every unmet criterion, in evaluation order."""
        return tuple(
            c.reason_code for c in self.criteria if not c.met and c.reason_code is not None
        )


class RefinementEntry(BaseModel):
    """One refined multiplier for ``(category, time_of_day_band)``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    category: TaskCategory
    time_of_day_band: TimeOfDayBand
    multiplier: float = Field(gt=0.0)
    sample_size: int = Field(ge=1)
    weighted_sample: float = Field(gt=0.0)
    observed_ratio: float = Field(gt=0.0)


class PerUserRefinement(BaseModel):
    """Finer per-user multipliers; exists only behind the power-user gate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    user_id: str = Field(min_length=1)
    computed_at: datetime
    entries: list[RefinementEntry] = Field(default_factory=list)

    @model_validator(mode="after")
    def _computed_at_aware(self) -> PerUserRefinement:
        if self.computed_at.tzinfo is None:
            raise ValueError("computed_at must be timezone-aware")
        return self

    @model_validator(mode="after")
    def _unique_keys(self) -> PerUserRefinement:
        keys = [(e.category.value, e.time_of_day_band.value) for e in self.entries]
        if len(set(keys)) != len(keys):
            raise ValueError("duplicate refinement key")
        return self

    def lookup(
        self, category: TaskCategory, band: TimeOfDayBand
    ) -> RefinementEntry | None:
        for entry in self.entries:
            if entry.category is category and entry.time_of_day_band is band:
                return entry
        return None
