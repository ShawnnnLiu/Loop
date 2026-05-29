"""``approval_event`` contract.

Canonical spec: ``docs/specs/approval-event.schema.md``.

An ``ApprovalEvent`` captures the explicit user authorization for a specific
draft schedule and hashed payload. The Calendar Write Manager rejects every
calendar write that lacks a matching ``approval_event_id`` whose hash check
passes at write time (axiom 06 lines 60-62, 181-189).

Approval records are immutable once created. The store enforces this at the
persistence boundary (see ``approval/store.py``); the model itself is
``frozen=True`` so in-process mutation is also impossible.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ApprovalActionType(StrEnum):
    """Allowed action types for an approval event (spec lines 47-53).

    Other action types must be explicitly defined before use.
    """

    ADD_TO_CALENDAR = "add_to_calendar"
    UPDATE_CALENDAR = "update_calendar"
    ROLLBACK_CALENDAR = "rollback_calendar"


class HashAlgorithm(StrEnum):
    """Allowed approval-payload hash algorithms (spec lines 55-59).

    Only ``sha256`` is supported for the MVP. The Calendar Write Manager
    rejects any unknown algorithm with
    ``ReasonCode.APPROVAL_HASH_ALGORITHM_UNSUPPORTED``.
    """

    SHA256 = "sha256"


_SHA256_PATTERN = r"^sha256:[0-9a-f]{64}$"


class ApprovalEvent(BaseModel):
    """User authorization for a specific draft schedule."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    approval_event_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    plan_id: str = Field(min_length=1)
    draft_schedule_id: str = Field(min_length=1)
    action_type: ApprovalActionType
    approved_payload_hash: str = Field(pattern=_SHA256_PATTERN)
    hash_algorithm: HashAlgorithm
    hash_canonicalization_version: str = Field(min_length=1)
    created_at: datetime
    expires_at: datetime

    @model_validator(mode="after")
    def _times_tz_aware(self) -> ApprovalEvent:
        if self.created_at.tzinfo is None or self.expires_at.tzinfo is None:
            raise ValueError("approval event created_at/expires_at must be timezone-aware")
        return self

    @model_validator(mode="after")
    def _expires_after_created(self) -> ApprovalEvent:
        if self.expires_at <= self.created_at:
            raise ValueError("approval event expires_at must be strictly after created_at")
        return self

    @model_validator(mode="after")
    def _hash_prefix_matches_algorithm(self) -> ApprovalEvent:
        expected_prefix = f"{self.hash_algorithm.value}:"
        if not self.approved_payload_hash.startswith(expected_prefix):
            raise ValueError(
                f"approved_payload_hash must start with {expected_prefix!r} "
                f"when hash_algorithm={self.hash_algorithm.value!r}"
            )
        return self
