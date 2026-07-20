"""``user_profile`` contract.

Canonical spec: ``docs/specs/user-profile.schema.md``.

The profile is the source of truth for planning and scheduling. It must be a
typed object, not a chat transcript. Required fields, validation rules, and
field semantics all follow the spec; update the spec first if the shape needs
to change.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from ._dedup import casefold_key, find_duplicates
from .common_types import HHMM, Day, EvidenceKind, ExperienceLevel
from .pathway_selection import PathwaySelection

PLAN_DIRECTION_MAX_CHARS = 4_000

THEME_TAGS_MAX_PER_ITEM = 5


class ExperienceItem(BaseModel):
    """One confirmed evidence entry (work, project, volunteering, ...).

    Profile vocabulary: lives here because the profile owns the confirmed
    values; ``resume_extraction`` (the ResumeIntakeNode proposal) imports it
    rather than redeclaring.

    The field name (and the profile's ``experience`` list name) predates the
    story layer and deliberately stays: ``kind`` / ``theme_tags`` landed as an
    additive amendment, not a rename/migration (narrative-pathways NP-A).
    ``theme_tags`` membership in the registry theme vocabulary is a
    service-layer check, not a contract-shape check.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    title: str = Field(min_length=1, max_length=120)
    organization: str | None = Field(default=None, min_length=1, max_length=120)
    summary: str | None = Field(default=None, min_length=1, max_length=280)
    kind: EvidenceKind = EvidenceKind.WORK
    theme_tags: list[Annotated[str, StringConstraints(min_length=1, max_length=60)]] = (
        Field(default_factory=list, max_length=THEME_TAGS_MAX_PER_ITEM)
    )

    @model_validator(mode="after")
    def _theme_tags_unique(self) -> ExperienceItem:
        dupes = find_duplicates([casefold_key(t) for t in self.theme_tags])
        if dupes:
            raise ValueError(
                f"theme_tags must be case-insensitively unique; duplicates: {dupes}"
            )
        return self


class DeepWorkWindow(BaseModel):
    """A weekly recurring deep-work block.

    ``start`` and ``end`` are local 24-hour times in the user's timezone;
    timezone semantics are owned by the surrounding profile, not this object.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    day: Day
    start: HHMM
    end: HHMM

    @model_validator(mode="after")
    def _start_before_end(self) -> DeepWorkWindow:
        if self.start >= self.end:
            raise ValueError(
                f"deep_work_window start ({self.start}) must be before end ({self.end})"
            )
        return self


class HardConstraints(BaseModel):
    """Non-negotiable scheduling boundaries."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    no_events_before: HHMM
    no_events_after: HHMM
    allow_weekends: bool = True
    max_daily_study_min: int = Field(gt=0, le=24 * 60)
    min_break_between_deep_blocks_min: int = Field(ge=0, le=12 * 60)

    @model_validator(mode="after")
    def _bounds_make_sense(self) -> HardConstraints:
        if self.no_events_before >= self.no_events_after:
            raise ValueError(
                f"no_events_before ({self.no_events_before}) must be earlier than "
                f"no_events_after ({self.no_events_after})"
            )
        return self


class Preferences(BaseModel):
    """Soft preferences used as tie-breakers when multiple schedules are valid."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    prefer_evening_sessions: bool = False
    prefer_weekend_long_blocks: bool = False
    avoid_back_to_back_deep_work: bool = False


class UserProfile(BaseModel):
    """Structured user profile (see ``docs/specs/user-profile.schema.md``)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    user_id: str = Field(min_length=1)
    profile_version: str = Field(min_length=1)
    goal: str = Field(min_length=1)
    target_role: str = Field(min_length=1)
    target_companies: list[str] = Field(default_factory=list)
    target_level: str | None = None
    timeline_weeks: int = Field(gt=0)
    weekly_hours: float = Field(gt=0, le=40)
    experience_level: ExperienceLevel
    known_strengths: list[str] = Field(default_factory=list)
    known_weaknesses: list[str] = Field(default_factory=list)
    experience: list[ExperienceItem] = Field(default_factory=list, max_length=20)
    """Confirmed work-experience entries; user-editable profile data.

    Not consumed by Strategist/Planner prompts — see the spec's normative
    Prompt Exposure table.
    """
    skills: list[Annotated[str, StringConstraints(min_length=1, max_length=60)]] = Field(
        default_factory=list, max_length=40
    )
    """Tools/stack tokens, distinct from ``known_strengths`` (broader capabilities).

    Display strings: extraction-matched skills are stored under their canonical
    taxonomy ``display_name``, but the user may hand-type anything — the
    vocabulary constrains the LLM, not the person.
    """
    preferred_session_length_min: int = Field(gt=0, le=12 * 60)
    max_session_length_min: int = Field(gt=0, le=12 * 60)
    deep_work_windows: list[DeepWorkWindow] = Field(default_factory=list)
    hard_constraints: HardConstraints
    preferences: Preferences = Field(default_factory=Preferences)
    motivation_profile_id: str | None = None
    resume_text: str | None = None
    """Optional raw résumé text the user pastes during onboarding.

    Raw context with exactly two consumers: the Strategist (appended as a
    labeled raw block) and the ResumeIntakeNode (extract→review→confirm
    input). Never an oracle for routing or validation. ``None`` when the user
    skips the step. PII: stored on the user's own profile, not persisted in the
    LLM call log, never used for training.
    """
    plan_direction: str | None = Field(
        default=None, min_length=1, max_length=PLAN_DIRECTION_MAX_CHARS
    )
    """Optional freeform plan the user pastes during onboarding: their own
    proposed steps toward the goal. Untrusted raw context with exactly one
    consumer: the Strategist (appended as a labeled raw block — see the
    spec's Prompt Exposure table). Never an oracle for routing or
    validation. ``None`` when the user skips the box. Stored on the user's
    own profile only, hashed (never raw) in the LLM call log, never used
    for training."""
    pathway_selection: PathwaySelection | None = None
    """Optional confirmed pathway choice (``pathway-selection.schema.md``).

    ``None`` = the user skipped the Your-story step; every downstream surface
    behaves exactly as today. Reaches the Strategist as typed constraints
    only (``pathway_id`` + computed ``unfilled_slots`` in
    ``StrategyConstraints``), never through the profile bundle - see the
    spec's Prompt Exposure table."""
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def _plan_direction_no_control_chars(self) -> UserProfile:
        if self.plan_direction is not None:
            bad = sorted(
                {
                    f"U+{ord(c):04X}"
                    for c in self.plan_direction
                    if ord(c) < 0x20 and c not in "\n\r\t"
                }
            )
            if bad:
                raise ValueError(f"plan_direction contains control characters: {bad}")
        return self

    @model_validator(mode="after")
    def _skills_unique(self) -> UserProfile:
        dupes = find_duplicates([casefold_key(s) for s in self.skills])
        if dupes:
            raise ValueError(f"skills must be case-insensitively unique; duplicates: {dupes}")
        return self

    @model_validator(mode="after")
    def _max_geq_preferred(self) -> UserProfile:
        if self.max_session_length_min < self.preferred_session_length_min:
            raise ValueError(
                "max_session_length_min must be >= preferred_session_length_min "
                f"(max={self.max_session_length_min}, "
                f"preferred={self.preferred_session_length_min})"
            )
        return self

    @model_validator(mode="after")
    def _timestamps_aware(self) -> UserProfile:
        if self.created_at.tzinfo is None or self.updated_at.tzinfo is None:
            raise ValueError("created_at and updated_at must be timezone-aware")
        if self.updated_at < self.created_at:
            raise ValueError("updated_at must not precede created_at")
        return self

    @model_validator(mode="after")
    def _slot_overrides_reference_experience(self) -> UserProfile:
        """Every slot override must name an experience item that exists here.

        Referential integrity the profile can enforce because it owns both
        halves: ``PathwaySelection`` alone cannot see the ``experience`` list,
        so a ``SlotOverride`` pointing at an item the user never entered is
        caught at parse time rather than surfacing later in the kernel. Uses
        the same case-insensitive ``(title, organization)`` identity as the
        override-uniqueness check.
        """
        if self.pathway_selection is None:
            return self
        item_keys = {
            (casefold_key(item.title), casefold_key(item.organization or ""))
            for item in self.experience
        }
        missing = sorted(
            f"({override.item_title!r}, {override.item_organization!r})"
            for override in self.pathway_selection.slot_overrides
            if (
                casefold_key(override.item_title),
                casefold_key(override.item_organization or ""),
            )
            not in item_keys
        )
        if missing:
            raise ValueError(
                "pathway_selection.slot_overrides reference experience items that "
                f"do not exist in this profile: {missing}"
            )
        return self
