"""``consent_record`` contract.

Canonical spec: ``docs/specs/consent-record.schema.md``.

A :class:`ConsentRecord` is the deterministic, auditable record that one user
granted (or has since revoked) one explicit data-use scope. Axiom 07 forbids
cross-user training data without opt-in; this record *is* the opt-in. The
consent gate consults it at training time **and** serving time (ADR-0007).

A record is created in ``granted`` status by the explicit user action of
granting — the record is the grant. Revocation is a lifecycle transition,
never a deletion, so consent history stays auditable. Re-consent after
revocation is a new record (see ``consent/store.py``); a revoked row is never
reactivated. The model is ``frozen=True`` so in-process mutation is
impossible.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ConsentScope(StrEnum):
    """The single data-use a consent record covers (spec "Field Definitions").

    One record covers exactly one scope; consenting to both scopes produces
    two records.
    """

    POOLED_TRAINING = "pooled_training"
    COHORT_RETRIEVAL = "cohort_retrieval"


class ConsentStatus(StrEnum):
    """Lifecycle state (spec "Lifecycle")."""

    GRANTED = "granted"
    REVOKED = "revoked"


#: Allowed status transitions. ``revoked`` is terminal; re-consent is a new
#: record, never a reactivation.
ALLOWED_CONSENT_TRANSITIONS: dict[ConsentStatus, frozenset[ConsentStatus]] = {
    ConsentStatus.GRANTED: frozenset({ConsentStatus.REVOKED}),
    ConsentStatus.REVOKED: frozenset(),
}


def is_allowed_consent_transition(current: ConsentStatus, nxt: ConsentStatus) -> bool:
    """Return True iff ``current → nxt`` is a permitted lifecycle transition."""
    return nxt in ALLOWED_CONSENT_TRANSITIONS[current]


class ConsentRecord(BaseModel):
    """One user's grant (or revocation) of one explicit data-use scope."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    consent_record_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    scope: ConsentScope
    status: ConsentStatus
    consent_version: str = Field(min_length=1)
    granted_at: datetime
    revoked_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def _timestamps_aware(self) -> ConsentRecord:
        fields = {
            "granted_at": self.granted_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "revoked_at": self.revoked_at,
        }
        for name, value in fields.items():
            if value is not None and value.tzinfo is None:
                raise ValueError(f"{name} must be timezone-aware")
        if self.updated_at < self.created_at:
            raise ValueError("updated_at must not precede created_at")
        if self.revoked_at is not None and self.revoked_at < self.granted_at:
            raise ValueError("revoked_at must not precede granted_at")
        return self

    @model_validator(mode="after")
    def _status_timestamp_consistency(self) -> ConsentRecord:
        if self.status is ConsentStatus.GRANTED and self.revoked_at is not None:
            raise ValueError("granted status must have null revoked_at")
        if self.status is ConsentStatus.REVOKED and self.revoked_at is None:
            raise ValueError("revoked status requires revoked_at")
        return self

    def is_active(self) -> bool:
        """Return True iff this record currently authorizes its scope."""
        return self.status is ConsentStatus.GRANTED
