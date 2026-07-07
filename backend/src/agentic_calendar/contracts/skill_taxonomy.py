"""``skill_taxonomy`` contract.

Canonical spec: ``docs/specs/skill-taxonomy.schema.md``.

The controlled skill vocabulary (axiom 08 "Controlled Vocabularies"):
canonical, versioned, human-curated data stored as checked-in JSON under
``backend/taxonomy/``. LLMs never write entries — extraction nodes emit
surface strings and a deterministic normalizer resolves them here via the
alias table. Aliases are globally unique across the taxonomy so resolution
is unambiguous by construction.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .career_track import CareerTrack


class SkillKind(StrEnum):
    """What kind of thing a taxonomy entry names."""

    LANGUAGE = "language"
    FRAMEWORK = "framework"
    TOOL = "tool"
    CONCEPT = "concept"
    PRACTICE = "practice"


class CorpusEvidence(BaseModel):
    """Corpus-derived annotation for one entry (filled only by RI-F enrichment).

    Evidence informs human curation; it never auto-creates, auto-deletes, or
    auto-ranks entries.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    snapshot_id: str = Field(min_length=1)
    occurrence_count: int = Field(ge=0)
    supporting_doc_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _doc_ids_unique(self) -> CorpusEvidence:
        if len(set(self.supporting_doc_ids)) != len(self.supporting_doc_ids):
            dupes = sorted(
                {d for d in self.supporting_doc_ids if self.supporting_doc_ids.count(d) > 1}
            )
            raise ValueError(f"duplicate supporting_doc_ids: {dupes}")
        return self


class SkillEntry(BaseModel):
    """One canonical skill with the aliases that resolve to it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    skill_id: str = Field(pattern=r"^skill\.[a-z0-9-]+$")
    display_name: str = Field(min_length=1, max_length=60)
    aliases: list[str] = Field(min_length=1)
    track_tags: list[CareerTrack] = Field(min_length=1)
    kind: SkillKind
    corpus_evidence: CorpusEvidence | None = None

    @field_validator("aliases")
    @classmethod
    def _aliases_normalized_and_unique(cls, aliases: list[str]) -> list[str]:
        for alias in aliases:
            if not alias:
                raise ValueError("aliases must be non-empty")
            if alias != " ".join(alias.lower().split()):
                raise ValueError(
                    f"alias {alias!r} must be stored lowercase-normalized "
                    "(lowercase, single-spaced, trimmed)"
                )
        if len(set(aliases)) != len(aliases):
            dupes = sorted({a for a in aliases if aliases.count(a) > 1})
            raise ValueError(f"duplicate aliases within entry: {dupes}")
        return aliases

    @field_validator("track_tags")
    @classmethod
    def _tracks_unique(cls, tracks: list[CareerTrack]) -> list[CareerTrack]:
        if len(set(tracks)) != len(tracks):
            dupes = sorted({t.value for t in tracks if tracks.count(t) > 1})
            raise ValueError(f"duplicate track_tags: {dupes}")
        return tracks


class SkillTaxonomy(BaseModel):
    """A versioned vocabulary: unique entry ids, globally unique aliases."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    taxonomy_version: str = Field(pattern=r"^skill-taxonomy-v\d+$")
    entries: list[SkillEntry] = Field(min_length=1)

    @model_validator(mode="after")
    def _ids_unique(self) -> SkillTaxonomy:
        ids = [e.skill_id for e in self.entries]
        if len(set(ids)) != len(ids):
            dupes = sorted({i for i in ids if ids.count(i) > 1})
            raise ValueError(f"duplicate skill_id values: {dupes}")
        return self

    @model_validator(mode="after")
    def _aliases_globally_unique(self) -> SkillTaxonomy:
        seen: dict[str, str] = {}
        collisions: list[str] = []
        for entry in self.entries:
            for alias in entry.aliases:
                if alias in seen:
                    collisions.append(
                        f"{alias!r} ({seen[alias]} and {entry.skill_id})"
                    )
                else:
                    seen[alias] = entry.skill_id
        if collisions:
            raise ValueError(
                "aliases must be globally unique across the taxonomy: "
                + ", ".join(sorted(collisions))
            )
        return self
