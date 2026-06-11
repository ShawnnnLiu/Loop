"""Tests for ``ConsentGate``: typed allow/deny, fully audited, both times.

The phase plan requires opt-out to be honored at training time AND serving
time. These tests prove the gate primitive both 6b paths build on: a revoke
flips the very next check — training or serving — to ``CONSENT_REVOKED``.
"""

from __future__ import annotations

import pytest

from agentic_calendar.common.clock import FrozenClock
from agentic_calendar.common.ids import DeterministicIdGenerator
from agentic_calendar.consent.audit_store import InMemoryDataAccessAuditStore
from agentic_calendar.consent.gate import GATED_PURPOSE_TO_SCOPE, ConsentGate
from agentic_calendar.consent.store import InMemoryConsentStore
from agentic_calendar.contracts.consent_record import ConsentScope
from agentic_calendar.contracts.data_access_audit import (
    DataAccessor,
    DataAccessOutcome,
    DataAccessPurpose,
)
from agentic_calendar.contracts.reason_codes import ReasonCode

from ._builders import T0, build_consent_record


def _gate(
    required_consent_version: str | None = None,
) -> tuple[ConsentGate, InMemoryConsentStore, InMemoryDataAccessAuditStore]:
    consents = InMemoryConsentStore(clock=FrozenClock(T0))
    audit = InMemoryDataAccessAuditStore()
    gate = ConsentGate(
        consents,
        audit,
        clock=FrozenClock(T0),
        id_generator=DeterministicIdGenerator(),
        required_consent_version=required_consent_version,
    )
    return gate, consents, audit


def test_active_grant_allows_and_audits() -> None:
    gate, consents, audit = _gate()
    consents.grant(build_consent_record())
    decision = gate.check(
        "user_123", DataAccessPurpose.POOLED_TRAINING, DataAccessor.TRAINING_PIPELINE
    )
    assert decision.allowed is True
    assert decision.reason_code is None
    entries = audit.list_for_user("user_123")
    assert len(entries) == 1
    assert entries[0] is decision.audit_entry
    assert entries[0].outcome is DataAccessOutcome.ALLOWED
    assert entries[0].purpose is DataAccessPurpose.POOLED_TRAINING
    assert entries[0].accessor is DataAccessor.TRAINING_PIPELINE
    assert entries[0].created_at == T0


def test_no_record_denies_with_consent_missing() -> None:
    gate, _, audit = _gate()
    decision = gate.check(
        "user_123", DataAccessPurpose.POOLED_TRAINING, DataAccessor.TRAINING_PIPELINE
    )
    assert decision.allowed is False
    assert decision.reason_code is ReasonCode.CONSENT_MISSING
    assert audit.list_for_user("user_123")[0].reason_code is ReasonCode.CONSENT_MISSING


def test_revoked_record_denies_with_consent_revoked() -> None:
    gate, consents, _ = _gate()
    consents.grant(build_consent_record())
    consents.revoke("consent_001")
    decision = gate.check(
        "user_123", DataAccessPurpose.POOLED_TRAINING, DataAccessor.TRAINING_PIPELINE
    )
    assert decision.allowed is False
    assert decision.reason_code is ReasonCode.CONSENT_REVOKED


def test_revocation_honored_at_serving_time_immediately() -> None:
    """Serving lookups stop the moment consent is revoked, not at next train."""
    gate, consents, audit = _gate()
    consents.grant(build_consent_record())
    before = gate.check(
        "user_123", DataAccessPurpose.POOLED_SERVING, DataAccessor.SERVING_PIPELINE
    )
    assert before.allowed is True
    consents.revoke("consent_001")
    after = gate.check(
        "user_123", DataAccessPurpose.POOLED_SERVING, DataAccessor.SERVING_PIPELINE
    )
    assert after.allowed is False
    assert after.reason_code is ReasonCode.CONSENT_REVOKED
    # Both checks were audited — the denial is visible in the log.
    outcomes = [e.outcome for e in audit.list_for_user("user_123")]
    assert outcomes == [DataAccessOutcome.ALLOWED, DataAccessOutcome.DENIED]


def test_regrant_restores_access() -> None:
    gate, consents, _ = _gate()
    consents.grant(build_consent_record())
    consents.revoke("consent_001")
    consents.grant(build_consent_record(consent_record_id="consent_002"))
    decision = gate.check(
        "user_123", DataAccessPurpose.POOLED_TRAINING, DataAccessor.TRAINING_PIPELINE
    )
    assert decision.allowed is True


def test_scopes_are_independent() -> None:
    gate, consents, _ = _gate()
    consents.grant(build_consent_record())  # pooled_training only
    retrieval = gate.check(
        "user_123", DataAccessPurpose.COHORT_RETRIEVAL, DataAccessor.RETRIEVAL_PIPELINE
    )
    assert retrieval.allowed is False
    assert retrieval.reason_code is ReasonCode.CONSENT_MISSING


def test_pooled_serving_consults_pooled_training_scope() -> None:
    assert GATED_PURPOSE_TO_SCOPE[DataAccessPurpose.POOLED_SERVING] is (
        ConsentScope.POOLED_TRAINING
    )
    gate, consents, _ = _gate()
    consents.grant(build_consent_record())
    decision = gate.check(
        "user_123", DataAccessPurpose.POOLED_SERVING, DataAccessor.SERVING_PIPELINE
    )
    assert decision.allowed is True


def test_stale_consent_version_denies_as_missing() -> None:
    gate, consents, _ = _gate(required_consent_version="2026-07")
    consents.grant(build_consent_record(consent_version="2026-06"))
    decision = gate.check(
        "user_123", DataAccessPurpose.POOLED_TRAINING, DataAccessor.TRAINING_PIPELINE
    )
    assert decision.allowed is False
    assert decision.reason_code is ReasonCode.CONSENT_MISSING


def test_matching_consent_version_allows() -> None:
    gate, consents, _ = _gate(required_consent_version="2026-06")
    consents.grant(build_consent_record(consent_version="2026-06"))
    decision = gate.check(
        "user_123", DataAccessPurpose.POOLED_TRAINING, DataAccessor.TRAINING_PIPELINE
    )
    assert decision.allowed is True


@pytest.mark.parametrize(
    "purpose",
    [DataAccessPurpose.DATA_VIEW, DataAccessPurpose.DATA_EXPORT, DataAccessPurpose.DATA_DELETE],
    ids=lambda p: p.value,
)
def test_data_control_purposes_rejected(purpose: DataAccessPurpose) -> None:
    gate, _, audit = _gate()
    with pytest.raises(ValueError, match="data control"):
        gate.check("user_123", purpose, DataAccessor.OPERATOR_CLI)
    assert audit.all() == []


def test_every_check_writes_exactly_one_entry() -> None:
    gate, consents, audit = _gate()
    consents.grant(build_consent_record())
    for _ in range(3):
        gate.check(
            "user_123", DataAccessPurpose.POOLED_TRAINING, DataAccessor.TRAINING_PIPELINE
        )
    gate.check("user_456", DataAccessPurpose.POOLED_TRAINING, DataAccessor.TRAINING_PIPELINE)
    assert len(audit.all()) == 4
    assert len(audit.list_for_user("user_456")) == 1
