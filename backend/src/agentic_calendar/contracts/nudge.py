"""``nudge`` contract.

Canonical spec: ``docs/specs/nudge.schema.md`` (axiom 21).

:class:`NudgeRecord` is the append-only audit record for one private user
nudge. Nudges are user-private — no sponsor or external party is ever
addressed (golden scenario 16). The record stores identifiers and outcome
metadata only: wording may be LLM-generated at render time, but the message
body is never stored and never becomes control-plane state (same privacy rule
as ``notification_log``).

Quiet hours defer, never drop: a nudge requested inside the contract's quiet
window is recorded as ``deferred_quiet_hours`` with ``deliver_at`` at the next
quiet-hours end boundary. The deferral math lives in
``accountability/nudges.py``; this module enforces only the record's internal
consistency.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .motivation_profile import NudgeChannel
from .reason_codes import ReasonCode


class NudgeStatus(StrEnum):
    SENT = "sent"
    DEFERRED_QUIET_HOURS = "deferred_quiet_hours"
    DRY_RUN = "dry_run"


class NudgeToneTier(StrEnum):
    """Deterministic tone tier the LLM must render within (Phase 6d).

    Selected from ``pressure_tolerance`` by contract derivation
    (accountability-contract spec "Tone Tier"); never chosen by the LLM,
    never free text, never a psychological label.
    """

    GENTLE = "gentle"
    STANDARD = "standard"
    DIRECT = "direct"


#: The only reason codes a private nudge may carry (spec "Field Definitions").
ALLOWED_NUDGE_REASON_CODES: frozenset[ReasonCode] = frozenset(
    {
        ReasonCode.MISSED_TASK_THRESHOLD_REACHED,
        ReasonCode.CHECKIN_DUE,
        ReasonCode.CHECKIN_MISSED,
        ReasonCode.LOW_COMPLETION_RATE,
        ReasonCode.USER_RECOMMITMENT_REQUIRED,
    }
)

#: Reason codes that may ask for recommitment (the direct/escalation nudge).
_RECOMMITMENT_REASON_CODES: frozenset[ReasonCode] = frozenset(
    {
        ReasonCode.MISSED_TASK_THRESHOLD_REACHED,
        ReasonCode.USER_RECOMMITMENT_REQUIRED,
    }
)


class NudgeRecord(BaseModel):
    """Append-only audit record for one private nudge delivery attempt."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    nudge_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    plan_id: str = Field(min_length=1)
    decision_id: str = Field(min_length=1)
    reason_code: ReasonCode
    channel: NudgeChannel
    tone_tier: NudgeToneTier
    status: NudgeStatus
    recommitment_requested: bool
    created_at: datetime
    deliver_at: datetime

    @model_validator(mode="after")
    def _reason_code_is_nudge_trigger(self) -> NudgeRecord:
        """Sponsor and calendar outcomes are never delivered as private nudges."""
        if self.reason_code not in ALLOWED_NUDGE_REASON_CODES:
            raise ValueError(
                f"reason_code '{self.reason_code.value}' is not a private nudge trigger"
            )
        return self

    @model_validator(mode="after")
    def _recommitment_only_on_escalation(self) -> NudgeRecord:
        if self.recommitment_requested and self.reason_code not in _RECOMMITMENT_REASON_CODES:
            raise ValueError(
                "recommitment_requested requires an escalation reason code "
                "(MISSED_TASK_THRESHOLD_REACHED or USER_RECOMMITMENT_REQUIRED)"
            )
        return self

    @model_validator(mode="after")
    def _timestamps_aware(self) -> NudgeRecord:
        if self.created_at.tzinfo is None or self.deliver_at.tzinfo is None:
            raise ValueError("created_at and deliver_at must be timezone-aware")
        return self

    @model_validator(mode="after")
    def _deliver_at_matches_status(self) -> NudgeRecord:
        """Deferred nudges deliver later; sent/dry-run resolve immediately."""
        if self.status is NudgeStatus.DEFERRED_QUIET_HOURS:
            if self.deliver_at <= self.created_at:
                raise ValueError("deferred_quiet_hours requires deliver_at after created_at")
        else:
            if self.deliver_at != self.created_at:
                raise ValueError(
                    f"status '{self.status.value}' requires deliver_at == created_at; "
                    "a future deliver_at means the nudge should have been deferred"
                )
        return self
