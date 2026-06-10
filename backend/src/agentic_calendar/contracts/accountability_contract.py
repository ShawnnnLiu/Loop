"""``accountability_contract`` contract.

Canonical spec: ``docs/specs/accountability-contract.schema.md`` (axiom 21).

:class:`AccountabilityContract` is the deterministic, versioned derivation of
a :class:`~agentic_calendar.contracts.motivation_profile.MotivationProfile`
that the Accountability Policy Engine reads. It snapshots the source
``profile_version`` and records *effective* thresholds (profile values scaled
by pressure tolerance) so every intervention decision is traceable to the
exact preferences that produced it.

``active: false`` is the deterministic kill switch: it stops both intervention
lanes with ``ACCOUNTABILITY_CONTRACT_INACTIVE`` (golden scenario 24) without
touching the motivation profile or the active plan. The derivation function
lives in ``accountability/contract.py``; this module owns only the shape.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .common_types import HHMM, Day
from .motivation_profile import (
    NudgeChannel,
    QuietHours,
    RecoveryPreference,
    SponsorVisibility,
)


class AccountabilityContract(BaseModel):
    """Effective accountability terms derived from one motivation profile."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    motivation_profile_id: str = Field(min_length=1)
    profile_version: str = Field(min_length=1)
    active: bool
    weekly_checkin_enabled: bool
    weekly_checkin_day: Day | None
    weekly_checkin_time: HHMM | None
    effective_missed_task_escalation_threshold: int = Field(ge=1, le=14)
    effective_behind_schedule_intervention_threshold_pct: int = Field(ge=5, le=50)
    low_completion_rate_floor: float = Field(gt=0.0, lt=1.0)
    checkin_grace_hours: int = Field(ge=1, le=168)
    recovery_mode_preference: RecoveryPreference
    sponsor_reporting_allowed: bool
    sponsor_visibility_level: SponsorVisibility
    sponsor_id: str | None
    nudge_channel_preference: NudgeChannel
    quiet_hours: QuietHours
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def _checkin_cadence_required_when_enabled(self) -> AccountabilityContract:
        if self.weekly_checkin_enabled and (
            self.weekly_checkin_day is None or self.weekly_checkin_time is None
        ):
            raise ValueError(
                "weekly_checkin_day and weekly_checkin_time are required when "
                "weekly_checkin_enabled is true"
            )
        return self

    @model_validator(mode="after")
    def _sponsor_consistency(self) -> AccountabilityContract:
        """Mirrors the motivation-profile sponsor rules on the snapshot."""
        if self.sponsor_reporting_allowed:
            if self.sponsor_visibility_level is SponsorVisibility.NONE:
                raise ValueError(
                    "sponsor_visibility_level must not be 'none' when "
                    "sponsor_reporting_allowed is true"
                )
            if self.sponsor_id is None:
                raise ValueError("sponsor_id is required when sponsor_reporting_allowed is true")
        else:
            if self.sponsor_visibility_level is not SponsorVisibility.NONE:
                raise ValueError(
                    "sponsor_visibility_level must be 'none' when "
                    "sponsor_reporting_allowed is false"
                )
        return self

    @model_validator(mode="after")
    def _timestamps_aware(self) -> AccountabilityContract:
        if self.created_at.tzinfo is None or self.updated_at.tzinfo is None:
            raise ValueError("created_at and updated_at must be timezone-aware")
        if self.updated_at < self.created_at:
            raise ValueError("updated_at must not precede created_at")
        return self
