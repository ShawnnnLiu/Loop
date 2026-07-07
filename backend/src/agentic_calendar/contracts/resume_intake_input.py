"""``resume_intake_input`` contract.

Canonical spec: ``docs/specs/resume-intake-input.schema.md``.

The validated bundle handed to the ResumeIntakeNode: pasted résumé, draft
answers from earlier wizard steps (all optional — the wizard may be
partially filled), and the allowed weak-spot vocabulary the service resolved
from the skill taxonomy. Validated at the node boundary like
``StrategistInput`` so a malformed bundle is caught before generation.

This is the first LLM input that exists before any run; the service mints an
``intake-``-prefixed run_id for the call log.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from .common_types import ExperienceLevel

RESUME_TEXT_MIN_CHARS = 50
RESUME_TEXT_MAX_CHARS = 40_000


class DraftProfileContext(BaseModel):
    """Draft onboarding answers; every field optional (unanswered = ``None``)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    goal: str | None = Field(default=None, min_length=1)
    target_role: str | None = Field(default=None, min_length=1)
    experience_level: ExperienceLevel | None = None
    timeline_weeks: int | None = Field(default=None, gt=0)
    weekly_hours: float | None = Field(default=None, gt=0, le=40)


class ResumeIntakeInput(BaseModel):
    """Validated input bundle for the ResumeIntakeNode."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    user_id: str = Field(min_length=1)
    resume_text: str = Field(
        min_length=RESUME_TEXT_MIN_CHARS, max_length=RESUME_TEXT_MAX_CHARS
    )
    """PII and untrusted input: sent to the provider as a labeled
    data-not-instructions block, hashed (never raw) in the call log."""
    draft_context: DraftProfileContext = Field(default_factory=DraftProfileContext)
    allowed_weak_spots: list[
        Annotated[str, StringConstraints(min_length=1, max_length=60)]
    ] = Field(default_factory=list)
    """Track-relevant taxonomy slice, filled by the service — the node never
    imports the taxonomy kernel; the vocabulary arrives as plain data."""

    @model_validator(mode="after")
    def _weak_spots_unique(self) -> ResumeIntakeInput:
        lowered = [s.lower() for s in self.allowed_weak_spots]
        if len(set(lowered)) != len(lowered):
            dupes = sorted({s for s in lowered if lowered.count(s) > 1})
            raise ValueError(
                f"allowed_weak_spots must be case-insensitively unique; duplicates: {dupes}"
            )
        return self
