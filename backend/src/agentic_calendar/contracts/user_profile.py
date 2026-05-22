"""``user_profile`` contract.

Canonical spec: ``docs/specs/user-profile.schema.md``.

The profile is the source of truth for planning and scheduling. It must be a
typed object, not a chat transcript. Required fields, validation rules, and
field semantics all follow the spec; update the spec first if the shape needs
to change.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .common_types import HHMM, Day, ExperienceLevel


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

    user_id: str
    profile_version: str
    goal: str
    target_role: str
    target_companies: list[str] = Field(default_factory=list)
    target_level: str | None = None
    timeline_weeks: int = Field(gt=0)
    weekly_hours: float = Field(gt=0, le=40)
    experience_level: ExperienceLevel
    known_strengths: list[str] = Field(default_factory=list)
    known_weaknesses: list[str] = Field(default_factory=list)
    preferred_session_length_min: int = Field(gt=0, le=12 * 60)
    max_session_length_min: int = Field(gt=0, le=12 * 60)
    deep_work_windows: list[DeepWorkWindow] = Field(default_factory=list)
    hard_constraints: HardConstraints
    preferences: Preferences = Field(default_factory=Preferences)
    motivation_profile_id: str | None = None
    created_at: datetime
    updated_at: datetime

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
