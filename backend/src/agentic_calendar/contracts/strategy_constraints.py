"""``strategy_constraints`` contract.

Canonical spec: ``docs/specs/syllabus-units.schema.md`` ("Strategist Inputs").

The deterministic bounds the Strategist must respect when proposing a syllabus.
The Strategist *proposes* modules; these constraints are part of what the
deterministic layer uses to *dispose* (gate / repair) its output.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .common_types import Priority


def _default_priority_values() -> list[Priority]:
    return [Priority.HIGH, Priority.MEDIUM, Priority.LOW]


class StrategyConstraints(BaseModel):
    """Bounds on a Strategist proposal (spec defaults shown)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    max_modules: int = Field(default=12, gt=0, le=100)
    required_priority_values: list[Priority] = Field(
        default_factory=_default_priority_values
    )
    max_total_estimated_minutes: int = Field(default=4800, gt=0)
    must_reference_claims_for_company_specific_modules: bool = True

    @model_validator(mode="after")
    def _priority_values_unique_nonempty(self) -> StrategyConstraints:
        if not self.required_priority_values:
            raise ValueError("required_priority_values must be non-empty")
        if len(set(self.required_priority_values)) != len(self.required_priority_values):
            raise ValueError("required_priority_values must not contain duplicates")
        return self
