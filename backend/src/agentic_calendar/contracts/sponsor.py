"""``sponsor`` contract.

Canonical spec: ``docs/specs/sponsor.schema.md``.

A :class:`Sponsor` is the deterministic record of a trusted third party who may
receive permissioned progress reports for one user. The row owns the *invite
lifecycle* (``pending`` → ``accepted`` → ``revoked``); the user's chosen
``sponsor_visibility_level`` lives on the ``motivation_profile``. No sponsor
report may be generated unless a sponsor row is in ``accepted`` status and the
motivation profile enables reporting against this ``sponsor_id`` (axiom 21).

Sponsor rows are append-only at the status level: each lifecycle transition
produces a new frozen instance with a refreshed ``updated_at`` (see
``accountability/sponsor_store.py``). The model is ``frozen=True`` so in-process
mutation is impossible.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .motivation_profile import NudgeChannel


class SponsorRelationship(StrEnum):
    """Coarse relationship label. Never raw identity (spec privacy note)."""

    PARENT = "parent"
    MENTOR = "mentor"
    COACH = "coach"
    PEER = "peer"
    OTHER = "other"


class SponsorStatus(StrEnum):
    """Invite lifecycle state (spec "Invite Lifecycle")."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    REVOKED = "revoked"


#: Allowed status transitions. ``revoked`` is terminal.
ALLOWED_SPONSOR_TRANSITIONS: dict[SponsorStatus, frozenset[SponsorStatus]] = {
    SponsorStatus.PENDING: frozenset({SponsorStatus.ACCEPTED, SponsorStatus.REVOKED}),
    SponsorStatus.ACCEPTED: frozenset({SponsorStatus.REVOKED}),
    SponsorStatus.REVOKED: frozenset(),
}


def is_allowed_sponsor_transition(current: SponsorStatus, nxt: SponsorStatus) -> bool:
    """Return True iff ``current → nxt`` is a permitted lifecycle transition."""
    return nxt in ALLOWED_SPONSOR_TRANSITIONS[current]


class Sponsor(BaseModel):
    """A trusted third party who may receive permissioned progress reports.

    The :class:`SponsorStatus` field reuses the channel enum from the
    motivation profile (``NudgeChannel``) for ``contact_channel`` so the two
    notions of "where do messages go" stay aligned.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    sponsor_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    relationship: SponsorRelationship
    contact_channel: NudgeChannel
    status: SponsorStatus
    invited_at: datetime
    accepted_at: datetime | None = None
    revoked_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def _timestamps_aware(self) -> Sponsor:
        fields = {
            "invited_at": self.invited_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "accepted_at": self.accepted_at,
            "revoked_at": self.revoked_at,
        }
        for name, value in fields.items():
            if value is not None and value.tzinfo is None:
                raise ValueError(f"{name} must be timezone-aware")
        if self.updated_at < self.created_at:
            raise ValueError("updated_at must not precede created_at")
        if self.accepted_at is not None and self.accepted_at < self.invited_at:
            raise ValueError("accepted_at must not precede invited_at")
        if self.revoked_at is not None and self.revoked_at < self.invited_at:
            raise ValueError("revoked_at must not precede invited_at")
        return self

    @model_validator(mode="after")
    def _status_timestamp_consistency(self) -> Sponsor:
        if self.status is SponsorStatus.PENDING:
            if self.accepted_at is not None or self.revoked_at is not None:
                raise ValueError("pending sponsor must have null accepted_at and revoked_at")
        elif self.status is SponsorStatus.ACCEPTED:
            if self.accepted_at is None:
                raise ValueError("accepted status requires accepted_at")
            if self.revoked_at is not None:
                raise ValueError("accepted status must have null revoked_at")
        elif self.status is SponsorStatus.REVOKED and self.revoked_at is None:
            raise ValueError("revoked status requires revoked_at")
        return self

    def is_reportable(self) -> bool:
        """Return True iff this sponsor may currently receive reports.

        Permission is the conjunction of the sponsor row being ``accepted`` and
        the motivation profile enabling reporting; this method covers only the
        row half. The Sponsor Report Generator combines it with the profile.
        """
        return self.status is SponsorStatus.ACCEPTED
