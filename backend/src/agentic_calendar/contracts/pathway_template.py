"""``pathway_template`` contract.

Canonical spec: ``docs/specs/pathway-template.schema.md``.

A :class:`PathwayTemplate` is a curated narrative package the user can choose
to build toward: a one-sentence story spine plus the evidence slots (pillars)
a coherent version of that story needs. Templates are canned, validated
literals owned by the pathway registry (NP-B), mirroring
``milestone_template``: this module only defines their *shape*. Registry-level
invariants (unique ``pathway_id``s, theme-vocabulary membership of
``required_themes_any``, taxonomy resolution of ``branch_skill_ids``, and the
prestige-term denylist) live in the registry's tests, not here.

LLMs do not author templates, rank pathways, or assign fit; pathway fit over
these templates is computed deterministically (axiom 00).
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from .career_track import CareerTrack
from .common_types import EvidenceKind

ThemeName = Annotated[str, StringConstraints(min_length=1, max_length=60)]


class EvidenceSlot(BaseModel):
    """One pillar of a pathway: the evidence a coherent story needs there.

    An evidence item matches a slot iff ``item.kind in required_kinds`` and
    ``item.theme_tags`` intersect ``required_themes_any`` (the ``narrative/``
    kernel owns that computation, NP-B). ``gap_module_hint`` and
    ``branch_skill_ids`` are display/seed data with no control-plane effect.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    slot_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    required_kinds: list[EvidenceKind] = Field(min_length=1)
    required_themes_any: list[ThemeName] = Field(min_length=1)
    min_items: int = Field(default=1, ge=1, le=10)
    gap_module_hint: str = Field(min_length=1)
    branch_skill_ids: list[Annotated[str, StringConstraints(min_length=1)]] = Field(
        min_length=1
    )

    @model_validator(mode="after")
    def _required_kinds_unique(self) -> EvidenceSlot:
        if len(set(self.required_kinds)) != len(self.required_kinds):
            dupes = sorted(
                {k.value for k in self.required_kinds if self.required_kinds.count(k) > 1}
            )
            raise ValueError(f"required_kinds must be unique; duplicates: {dupes}")
        return self

    @model_validator(mode="after")
    def _themes_unique(self) -> EvidenceSlot:
        lowered = [t.lower() for t in self.required_themes_any]
        if len(set(lowered)) != len(lowered):
            dupes = sorted({t for t in lowered if lowered.count(t) > 1})
            raise ValueError(
                f"required_themes_any must be case-insensitively unique; duplicates: {dupes}"
            )
        return self

    @model_validator(mode="after")
    def _branch_skill_ids_unique(self) -> EvidenceSlot:
        if len(set(self.branch_skill_ids)) != len(self.branch_skill_ids):
            dupes = sorted(
                {s for s in self.branch_skill_ids if self.branch_skill_ids.count(s) > 1}
            )
            raise ValueError(f"branch_skill_ids must be unique; duplicates: {dupes}")
        return self


class PathwayTemplate(BaseModel):
    """A curated narrative pathway for one :class:`CareerTrack`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    pathway_id: str = Field(min_length=1)
    pathway_schema_version: str = Field(min_length=1)
    career_track: CareerTrack
    display_name: str = Field(min_length=1)
    spine: str = Field(min_length=1)
    audience_note: str = Field(min_length=1)
    evidence_slots: list[EvidenceSlot] = Field(min_length=1)

    @model_validator(mode="after")
    def _slot_ids_unique(self) -> PathwayTemplate:
        ids = [s.slot_id for s in self.evidence_slots]
        if len(set(ids)) != len(ids):
            dupes = sorted({i for i in ids if ids.count(i) > 1})
            raise ValueError(f"evidence_slots must have unique slot_id values; duplicates: {dupes}")
        return self
