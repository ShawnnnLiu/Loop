"""``accountability_state`` contract.

Canonical spec: ``docs/specs/accountability-state.schema.md`` (axiom 21).

:class:`AccountabilityState` is the deterministic projection of telemetry and
check-in events against the accountability contract — the numbers that answer
"is this user behind?", which the LLM is forbidden from answering. Axiom 21:
the state "must be recomputed from source events, never edited in place"
(hence ``frozen=True``; recomputation builds a new object).

The projection itself (window math, behind-schedule formula, status
thresholds) lives in ``accountability/projection.py``; this module owns only
the shape. ``recommended_intervention`` uses the policy engine's
:class:`~agentic_calendar.contracts.accountability_intervention.AccountabilityAction`
vocabulary — the spec normalizes axiom 21's illustrative
``"recovery_checkin"`` string to this enum.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .accountability_intervention import AccountabilityAction
from .common_types import AccountabilityStatus
from .motivation_profile import SponsorVisibility


class AccountabilityState(BaseModel):
    """Deterministic accountability projection for one user and plan."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    user_id: str = Field(min_length=1)
    plan_id: str = Field(min_length=1)
    completion_rate_7d: float = Field(ge=0.0, le=1.0)
    completion_rate_14d: float = Field(ge=0.0, le=1.0)
    missed_tasks_7d: int = Field(ge=0)
    reschedule_count_7d: int = Field(ge=0)
    behind_schedule_percent: int = Field(ge=0, le=100)
    weekly_checkin_completed: bool
    current_status: AccountabilityStatus
    recommended_intervention: AccountabilityAction | None = None
    sponsor_report_allowed: bool
    sponsor_report_level: SponsorVisibility
    computed_at: datetime

    @model_validator(mode="after")
    def _sponsor_snapshot_consistency(self) -> AccountabilityState:
        """A disallowed sponsor path cannot carry a visibility level."""
        if self.sponsor_report_allowed:
            if self.sponsor_report_level is SponsorVisibility.NONE:
                raise ValueError(
                    "sponsor_report_level must not be 'none' when sponsor_report_allowed is true"
                )
        else:
            if self.sponsor_report_level is not SponsorVisibility.NONE:
                raise ValueError(
                    "sponsor_report_level must be 'none' when sponsor_report_allowed is false"
                )
        return self

    @model_validator(mode="after")
    def _computed_at_aware(self) -> AccountabilityState:
        if self.computed_at.tzinfo is None:
            raise ValueError("computed_at must be timezone-aware")
        return self
