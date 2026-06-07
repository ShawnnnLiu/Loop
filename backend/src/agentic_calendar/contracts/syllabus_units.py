"""``syllabus_units`` contract.

Canonical spec: ``docs/specs/syllabus-units.schema.md``.

Output of ``StrategistNode``. Must be structured, not prose
(see ``docs/decisions/ADR-0005-structured-syllabus-not-prose.md``).
The Validation Layer enforces graph and coverage constraints downstream;
this module is responsible only for *shape*.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .common_types import Priority


class SyllabusModule(BaseModel):
    """One structured learning module."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    module_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    priority: Priority
    reason: str | None = None
    target_outcomes: list[str] = Field(min_length=1)
    estimated_total_min: int = Field(gt=0)
    difficulty: int = Field(ge=1, le=5)
    source_claim_ids: list[str] = Field(default_factory=list)
    company_specific: bool = False
    """Whether this module is tailored to a specific target company.

    The Strategist *proposes* this flag; the deterministic validator *disposes*:
    when ``strategy_constraints.must_reference_claims_for_company_specific_modules``
    is set, a company-specific module must cite at least one ``source_claim_id``
    (syllabus-units spec; checked in ``validation/source_claims.py``, not here,
    because the rule needs the claim registry + the constraint flag). An explicit
    flag keeps "company-specific" deterministic rather than inferred from prose."""

    @model_validator(mode="after")
    def _high_priority_needs_reason(self) -> SyllabusModule:
        if self.priority is Priority.HIGH and (
            self.reason is None or not self.reason.strip()
        ):
            raise ValueError(
                f"high-priority module {self.module_id!r} must include a non-empty 'reason'"
            )
        return self


class SyllabusUnits(BaseModel):
    """Complete syllabus revision: ``syllabus_version`` + modules."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    syllabus_version: str = Field(min_length=1)
    goal_summary: str = Field(min_length=1)
    modules: list[SyllabusModule] = Field(min_length=1)

    @model_validator(mode="after")
    def _module_ids_unique(self) -> SyllabusUnits:
        seen: set[str] = set()
        dupes: list[str] = []
        for m in self.modules:
            if m.module_id in seen:
                dupes.append(m.module_id)
            seen.add(m.module_id)
        if dupes:
            raise ValueError(f"duplicate module_id values: {sorted(set(dupes))}")
        return self
