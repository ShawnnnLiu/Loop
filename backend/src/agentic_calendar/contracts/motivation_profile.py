"""``motivation_profile`` contract.

Canonical spec: ``docs/specs/motivation-profile.schema.md``.

This profile lives separately from ``user_profile`` because motivation state
changes (sponsor visibility, weekly check-in cadence) have a different
invalidation policy than planning state. Motivation must be deterministic
state, never inferred by the LLM.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .common_types import HHMM, Day


class Level(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RecoveryPreference(StrEnum):
    RESCHEDULE = "reschedule"
    SCOPE_REDUCTION = "scope_reduction"
    EXTEND_TIMELINE = "extend_timeline"
    ASK_EACH_TIME = "ask_each_time"


class SponsorVisibility(StrEnum):
    NONE = "none"
    SUMMARY_ONLY = "summary_only"
    MILESTONE_PROGRESS = "milestone_progress"
    TASK_COMPLETION = "task_completion"


class NudgeChannel(StrEnum):
    IN_APP = "in_app"
    EMAIL = "email"
    PUSH = "push"


class QuietHours(BaseModel):
    """A single contiguous quiet-hours window in HH:MM local time.

    ``end`` may legitimately be before ``start`` (overnight quiet hours), so
    we do **not** enforce ordering here — see the spec.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    start: HHMM
    end: HHMM


class MotivationProfile(BaseModel):
    """Accountability preferences and procrastination risk."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    motivation_profile_id: str
    user_id: str
    profile_version: str
    self_motivation_level: Level
    procrastination_risk: Level
    pressure_tolerance: Level
    weekly_checkin_enabled: bool
    weekly_checkin_day: Day | None = None
    weekly_checkin_time: HHMM | None = None
    missed_task_escalation_threshold: int = Field(default=2, ge=1, le=14)
    behind_schedule_intervention_threshold_pct: int = Field(default=20, ge=5, le=50)
    recovery_mode_preference: RecoveryPreference = RecoveryPreference.ASK_EACH_TIME
    sponsor_enabled: bool = False
    sponsor_visibility_level: SponsorVisibility = SponsorVisibility.NONE
    sponsor_id: str | None = None
    nudge_channel_preference: NudgeChannel = NudgeChannel.IN_APP
    quiet_hours: QuietHours = Field(
        default_factory=lambda: QuietHours(start="22:00", end="08:00")
    )
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def _checkin_required_when_enabled(self) -> MotivationProfile:
        if self.weekly_checkin_enabled and (
            self.weekly_checkin_day is None or self.weekly_checkin_time is None
        ):
            raise ValueError(
                "weekly_checkin_day and weekly_checkin_time are required when "
                "weekly_checkin_enabled is true"
            )
        return self

    @model_validator(mode="after")
    def _sponsor_consistency(self) -> MotivationProfile:
        if self.sponsor_enabled:
            if self.sponsor_visibility_level is SponsorVisibility.NONE:
                raise ValueError(
                    "sponsor_visibility_level must not be 'none' when sponsor_enabled is true"
                )
            if self.sponsor_id is None:
                raise ValueError("sponsor_id is required when sponsor_enabled is true")
        else:
            if self.sponsor_visibility_level is not SponsorVisibility.NONE:
                raise ValueError(
                    "sponsor_visibility_level must be 'none' when sponsor_enabled is false"
                )
        return self

    @model_validator(mode="after")
    def _timestamps_aware(self) -> MotivationProfile:
        if self.created_at.tzinfo is None or self.updated_at.tzinfo is None:
            raise ValueError("created_at and updated_at must be timezone-aware")
        if self.updated_at < self.created_at:
            raise ValueError("updated_at must not precede created_at")
        return self
