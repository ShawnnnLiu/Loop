"""``checkin_event`` contract.

Canonical spec: ``docs/specs/checkin-event.schema.md`` (axiom 21).

:class:`CheckinEvent` is the append-only record of one completed weekly
check-in. Whether a check-in is *due* or *missed* is never stored here — the
check-in evaluator computes that deterministically from the accountability
contract cadence and the clock (``CHECKIN_DUE`` / ``CHECKIN_MISSED``).

Control-plane boundary: ``user_selected_recovery_action`` is the only field
that may influence routing (an explicit enum the user chose).
``user_reported_blockers`` is private free text — never in sponsor reports,
never parsed into workflow state.

``checkin_id`` uniqueness / dedup is a store concern, not a single-object
invariant (same split as ``telemetry``).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RecoveryAction(StrEnum):
    """A concrete recovery choice the user can select.

    Deliberately excludes the motivation profile's ``ask_each_time``: that is
    a *preference* about when to ask, not an answer.
    """

    RESCHEDULE = "reschedule"
    SCOPE_REDUCTION = "scope_reduction"
    EXTEND_TIMELINE = "extend_timeline"


class CheckinEvent(BaseModel):
    """One submitted weekly check-in (append-only)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    checkin_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    plan_id: str = Field(min_length=1)
    week_start: date
    week_end: date
    completed_task_count: int = Field(ge=0)
    scheduled_task_count: int = Field(ge=0)
    completed_minutes: int = Field(ge=0)
    scheduled_minutes: int = Field(ge=0)
    user_reported_blockers: str | None = Field(default=None, max_length=2000)
    user_selected_recovery_action: RecoveryAction | None = None
    created_at: datetime

    @model_validator(mode="after")
    def _week_spans_seven_days(self) -> CheckinEvent:
        """The reported cycle is exactly one week (spec validation rules).

        ``completed_*`` values are intentionally not capped by ``scheduled_*``:
        a user may complete more than scheduled; behind-schedule math clamps
        at zero downstream instead.
        """
        if self.week_end != self.week_start + timedelta(days=6):
            raise ValueError("week_end must be exactly 6 days after week_start")
        return self

    @model_validator(mode="after")
    def _created_at_aware(self) -> CheckinEvent:
        if self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        return self
