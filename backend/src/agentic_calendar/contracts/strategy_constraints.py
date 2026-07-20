"""``strategy_constraints`` contract.

Canonical spec: ``docs/specs/strategy-constraints.schema.md`` (referenced by
``docs/specs/syllabus-units.schema.md`` "Strategist Inputs").

The deterministic bounds the Strategist must respect when proposing a syllabus.
The Strategist *proposes* modules; these constraints are part of what the
deterministic layer uses to *dispose* (gate / repair) its output.

The pathway fields (narrative-pathways NP-A) are filled by the composition
root from the profile's confirmed ``pathway_selection`` (NP-D): the
``narrative/`` kernel computes ``unfilled_slots`` deterministically and the
Strategist is *told* the gaps, never asked to find them. Defaults keep ``{}``
valid, so a profile without a selection produces today's bundle unchanged.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .common_types import Priority


def _default_priority_values() -> list[Priority]:
    return [Priority.HIGH, Priority.MEDIUM, Priority.LOW]


class UnfilledSlot(BaseModel):
    """One unfilled evidence slot, projected from the selected pathway.

    A display/seed projection of ``EvidenceSlot`` (pathway-template spec):
    ``gap_module_hint`` seeds module wording and is never control flow.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    slot_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    gap_module_hint: str = Field(min_length=1)


class StrategyConstraints(BaseModel):
    """Bounds on a Strategist proposal (spec defaults shown)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    max_modules: int = Field(default=12, gt=0, le=100)
    required_priority_values: list[Priority] = Field(
        default_factory=_default_priority_values
    )
    max_total_estimated_minutes: int = Field(default=4800, gt=0)
    must_reference_claims_for_company_specific_modules: bool = True
    pathway_id: str | None = Field(default=None, min_length=1)
    unfilled_slots: list[UnfilledSlot] = Field(default_factory=list)
    max_slot_modules: int = Field(default=3, gt=0, le=10)

    @model_validator(mode="after")
    def _priority_values_unique_nonempty(self) -> StrategyConstraints:
        if not self.required_priority_values:
            raise ValueError("required_priority_values must be non-empty")
        if len(set(self.required_priority_values)) != len(self.required_priority_values):
            raise ValueError("required_priority_values must not contain duplicates")
        return self

    @model_validator(mode="after")
    def _unfilled_slots_require_pathway(self) -> StrategyConstraints:
        if self.unfilled_slots and self.pathway_id is None:
            raise ValueError("unfilled_slots requires pathway_id (no pathway selected)")
        return self

    @model_validator(mode="after")
    def _unfilled_slot_ids_unique(self) -> StrategyConstraints:
        ids = [s.slot_id for s in self.unfilled_slots]
        if len(set(ids)) != len(ids):
            dupes = sorted({i for i in ids if ids.count(i) > 1})
            raise ValueError(f"unfilled_slots must have unique slot_id values; duplicates: {dupes}")
        return self
