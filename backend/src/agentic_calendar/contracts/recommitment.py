"""``recommitment`` contract.

Canonical spec: ``docs/specs/recommitment-event.schema.md`` (axiom 21
intervention table: "Direct nudge" / "Accountability reset").

:class:`RecommitmentRequest` is the system's explicit ask — re-approve the
plan, timeline, or intensity — emitted with ``USER_RECOMMITMENT_REQUIRED``
alongside a ``recommitment_requested`` nudge. :class:`RecommitmentEvent` is
the user's append-only answer.

Recommitment never mutates anything by itself: ``keep_plan`` records explicit
re-approval of the active plan version; every ``revise_*`` choice routes into
the existing draft → validation → diff → approval pipeline (axiom 15). The
deterministic next action per choice is the spec's "Choice Semantics" table.
Answer-once enforcement (a request is answered at most once) is a store
concern, like ``telemetry`` dedup.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .reason_codes import ReasonCode


class RecommitmentChoice(StrEnum):
    KEEP_PLAN = "keep_plan"
    REVISE_TIMELINE = "revise_timeline"
    REVISE_INTENSITY = "revise_intensity"
    REVISE_GOAL = "revise_goal"


class RecommitmentRequest(BaseModel):
    """The system's explicit recommitment ask."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    recommitment_request_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    plan_version: str = Field(min_length=1)
    decision_id: str = Field(min_length=1)
    reason_code: ReasonCode
    requested_at: datetime

    @model_validator(mode="after")
    def _reason_code_fixed(self) -> RecommitmentRequest:
        if self.reason_code is not ReasonCode.USER_RECOMMITMENT_REQUIRED:
            raise ValueError("a recommitment request carries exactly USER_RECOMMITMENT_REQUIRED")
        return self

    @model_validator(mode="after")
    def _requested_at_aware(self) -> RecommitmentRequest:
        if self.requested_at.tzinfo is None:
            raise ValueError("requested_at must be timezone-aware")
        return self


class RecommitmentEvent(BaseModel):
    """The user's explicit, append-only recommitment answer."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    recommitment_event_id: str = Field(min_length=1)
    recommitment_request_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    plan_version: str = Field(min_length=1)
    choice: RecommitmentChoice
    created_at: datetime

    @model_validator(mode="after")
    def _created_at_aware(self) -> RecommitmentEvent:
        if self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        return self
