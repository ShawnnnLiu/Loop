"""``skill_grouping`` contract (KT-A).

Canonical spec: ``docs/specs/skill-grouping.schema.md``.

A :class:`SkillGrouping` is a versioned overlay **beside** the skill taxonomy:
it curates, once per ``skill_id``, the group a skill belongs to, its per-skill
honed-threshold prior, and a display blurb. The deterministic knowledge-map
generator (``07-tree-generation.md``, KT-B) consumes it plus a
:class:`PathwayTemplate`'s slot seeds to emit a :class:`KnowledgeMap`.

This module defines only the *shape*: field bounds, unique ``group_id`` /
``skill_id`` lists, and that every entry's ``group_id`` is declared in
``groups``. Taxonomy resolution and demand-driven coverage (a row for every
skill reachable from any pathway's slot seeds and the add-picker slice) are
registry/generator concerns (KT-B), not single-object invariants.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from ._dedup import find_duplicates

GroupId = Annotated[str, StringConstraints(pattern=r"^kg-[a-z0-9-]+$")]


class SkillGroup(BaseModel):
    """One curated group: a named cluster skills are assigned to."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    group_id: GroupId
    title: str = Field(min_length=1)
    blurb: str = Field(min_length=1)


class SkillGroupingEntry(BaseModel):
    """One curated ``skill_id → group`` placement with its minutes prior."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    skill_id: str = Field(min_length=1)
    group_id: GroupId
    expected_minutes: int = Field(ge=1)
    blurb: str = Field(min_length=1)


class SkillGrouping(BaseModel):
    """A versioned skill grouping: groups + per-skill placement entries."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    skill_grouping_version: str = Field(min_length=1)
    taxonomy_version: str = Field(min_length=1)
    groups: list[SkillGroup] = Field(min_length=1)
    entries: list[SkillGroupingEntry] = Field(min_length=1)

    @model_validator(mode="after")
    def _group_ids_unique(self) -> SkillGrouping:
        dupes = find_duplicates([g.group_id for g in self.groups])
        if dupes:
            raise ValueError(f"group_id values must be unique; duplicates: {dupes}")
        return self

    @model_validator(mode="after")
    def _skill_ids_unique(self) -> SkillGrouping:
        dupes = find_duplicates([e.skill_id for e in self.entries])
        if dupes:
            raise ValueError(f"skill_id values must be unique; duplicates: {dupes}")
        return self

    @model_validator(mode="after")
    def _entry_groups_declared(self) -> SkillGrouping:
        declared = {g.group_id for g in self.groups}
        missing = sorted(
            {e.group_id for e in self.entries if e.group_id not in declared}
        )
        if missing:
            raise ValueError(
                f"entry group_id values not declared in groups: {missing}"
            )
        return self
