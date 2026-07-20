"""``resume_extraction`` contract.

Canonical spec: ``docs/specs/resume-extraction.schema.md``.

The schema-bound proposal the ResumeIntakeNode returns: candidates for
user-editable profile fields, reviewed and edited by the user before any
write. All lists default empty — empty over fabrication. Provenance is
structural (extracted / inferred / suggested, by field group); there are no
confidence values anywhere, and ``extra="forbid"`` keeps it that way.

The groundedness, denylist, and weak-spot-membership invariants need the
source résumé text / allowed vocabulary and are enforced by the adapter's
deterministic post-validator inside the bounded repair loop; this contract
enforces bounds and uniqueness.

Since narrative-pathways NP-A, each proposed ``ExperienceItem`` may carry
``kind`` + ``theme_tags`` (shape shared with the profile via the imported
model; defaults keep older extractions valid). The intake prompt starts
proposing them, and theme-vocabulary membership joins the repair loop, in
NP-C.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from .user_profile import ExperienceItem

ShortText = Annotated[str, StringConstraints(min_length=1, max_length=60)]


def _require_unique_lowered(items: list[str], field_name: str) -> None:
    lowered = [s.lower() for s in items]
    if len(set(lowered)) != len(lowered):
        dupes = sorted({s for s in lowered if lowered.count(s) > 1})
        raise ValueError(
            f"{field_name} must be case-insensitively unique; duplicates: {dupes}"
        )


class ResumeExtraction(BaseModel):
    """Proposed profile-field candidates from one résumé extraction."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    experience: list[ExperienceItem] = Field(default_factory=list, max_length=20)
    skills: list[ShortText] = Field(default_factory=list, max_length=40)
    known_strengths: list[ShortText] = Field(default_factory=list, max_length=15)
    inferred_weak_spots: list[ShortText] = Field(default_factory=list, max_length=15)
    target_company_categories: list[ShortText] = Field(default_factory=list, max_length=8)

    @model_validator(mode="after")
    def _lists_unique(self) -> ResumeExtraction:
        _require_unique_lowered(self.skills, "skills")
        _require_unique_lowered(self.known_strengths, "known_strengths")
        _require_unique_lowered(self.inferred_weak_spots, "inferred_weak_spots")
        _require_unique_lowered(
            self.target_company_categories, "target_company_categories"
        )
        return self

    @model_validator(mode="after")
    def _experience_unique(self) -> ResumeExtraction:
        keys = [
            (item.title.lower(), (item.organization or "").lower())
            for item in self.experience
        ]
        if len(set(keys)) != len(keys):
            dupes = sorted({k for k in keys if keys.count(k) > 1})
            raise ValueError(
                "experience entries must be unique by (title, organization), "
                f"case-insensitively; duplicates: {dupes}"
            )
        return self
