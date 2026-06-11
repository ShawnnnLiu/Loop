"""``data_access_audit`` contract.

Canonical spec: ``docs/specs/data-access-audit.schema.md``.

:class:`DataAccessAuditEntry` is the append-only audit record for every
consent-scoped data access and every user data-control operation (ADR-0007).
Every consent-gate check writes exactly one entry — allowed or denied — and
every view/export/delete operation writes one entry.

The log stores identifiers and outcome metadata only; it has no free-text
fields and must never contain telemetry payloads, task content, or calendar
text. Entries are retained even after a user's data is deleted: the
``DATA_DELETED`` entry is the proof the deletion happened.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .reason_codes import ReasonCode


class DataAccessPurpose(StrEnum):
    """Why the data was touched (spec "Allowed ``purpose`` Values")."""

    POOLED_TRAINING = "pooled_training"
    POOLED_SERVING = "pooled_serving"
    COHORT_RETRIEVAL = "cohort_retrieval"
    DATA_VIEW = "data_view"
    DATA_EXPORT = "data_export"
    DATA_DELETE = "data_delete"


class DataAccessor(StrEnum):
    """Which system component performed the access. Never a person."""

    OPERATOR_CLI = "operator_cli"
    TRAINING_PIPELINE = "training_pipeline"
    SERVING_PIPELINE = "serving_pipeline"
    RETRIEVAL_PIPELINE = "retrieval_pipeline"


class DataAccessOutcome(StrEnum):
    """Whether the access proceeded."""

    ALLOWED = "allowed"
    DENIED = "denied"


#: Purposes that are user data controls; never consent-denied (a user always
#: controls their own data).
DATA_CONTROL_PURPOSES: frozenset[DataAccessPurpose] = frozenset(
    {
        DataAccessPurpose.DATA_VIEW,
        DataAccessPurpose.DATA_EXPORT,
        DataAccessPurpose.DATA_DELETE,
    }
)

#: The only codes a denied entry may carry (spec "``reason_code`` Semantics").
_DENIAL_REASON_CODES: frozenset[ReasonCode] = frozenset(
    {ReasonCode.CONSENT_MISSING, ReasonCode.CONSENT_REVOKED}
)


class DataAccessAuditEntry(BaseModel):
    """Append-only audit record for one data access or data-control op."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    audit_entry_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    purpose: DataAccessPurpose
    accessor: DataAccessor
    outcome: DataAccessOutcome
    reason_code: ReasonCode | None = None
    created_at: datetime

    @model_validator(mode="after")
    def _created_at_aware(self) -> DataAccessAuditEntry:
        if self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        return self

    @model_validator(mode="after")
    def _denied_carries_consent_code(self) -> DataAccessAuditEntry:
        if self.outcome is not DataAccessOutcome.DENIED:
            return self
        if self.purpose in DATA_CONTROL_PURPOSES:
            raise ValueError("data-control purposes are never consent-denied")
        if self.reason_code not in _DENIAL_REASON_CODES:
            raise ValueError(
                "denied outcome requires reason_code CONSENT_MISSING or CONSENT_REVOKED"
            )
        return self

    @model_validator(mode="after")
    def _allowed_reason_code_matches_purpose(self) -> DataAccessAuditEntry:
        if self.outcome is not DataAccessOutcome.ALLOWED:
            return self
        if self.purpose is DataAccessPurpose.DATA_EXPORT:
            if self.reason_code is not ReasonCode.DATA_EXPORTED:
                raise ValueError("allowed data_export requires reason_code DATA_EXPORTED")
        elif self.purpose is DataAccessPurpose.DATA_DELETE:
            if self.reason_code is not ReasonCode.DATA_DELETED:
                raise ValueError("allowed data_delete requires reason_code DATA_DELETED")
        elif self.reason_code is not None:
            raise ValueError(
                f"allowed '{self.purpose.value}' access must have a null reason_code"
            )
        return self
