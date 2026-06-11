"""Tests for consent-gated cohort retrieval (Phase 6d).

The cohort cache namespace is reachable only behind the ``cohort_retrieval``
consent scope. The gate lives in ``consent/`` and is composed here by the
test (tests may cross regions; src may not): a denied gate yields
``cohort_id=None`` and the lookup is byte-identical to the global path.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from agentic_calendar.cache.cohort import (
    CohortLookupSource,
    cohort_lookup,
    cohort_scoped_key,
    derive_cohort_id,
)
from agentic_calendar.cache.keys import CacheKey, CacheTarget
from agentic_calendar.cache.store import CacheEntry, InMemoryCache
from agentic_calendar.common.clock import FrozenClock
from agentic_calendar.common.ids import DeterministicIdGenerator
from agentic_calendar.consent.audit_store import InMemoryDataAccessAuditStore
from agentic_calendar.consent.gate import ConsentGate
from agentic_calendar.consent.store import InMemoryConsentStore
from agentic_calendar.contracts.common_types import ExperienceLevel
from agentic_calendar.contracts.consent_record import ConsentRecord, ConsentScope
from agentic_calendar.contracts.data_access_audit import (
    DataAccessor,
    DataAccessPurpose,
)
from agentic_calendar.contracts.reason_codes import ReasonCode

T0 = datetime(2026, 6, 10, 16, 0, tzinfo=UTC)


def _key() -> CacheKey:
    return CacheKey.model_validate(
        {
            "target": CacheTarget.RAG_RETRIEVAL,
            "role_target": "Backend SWE",
            "freshness_window": "2026-06",
            "object_schema_version": "claims-v1",
        }
    )


def _entry(key: CacheKey, marker: str) -> CacheEntry:
    return CacheEntry(
        key=key,
        value_kind=key.target,
        value_json={"marker": marker},
        source_claim_ids=("claim_a",),
        created_at=T0,
    )


COHORT = derive_cohort_id(ExperienceLevel.INTERMEDIATE, "Backend SWE")


def test_derive_cohort_id_normalizes_deterministically() -> None:
    assert COHORT == "intermediate|backend swe"
    assert derive_cohort_id(ExperienceLevel.INTERMEDIATE, "  backend swe  ") == COHORT
    with pytest.raises(ValueError, match="non-empty"):
        derive_cohort_id(ExperienceLevel.BEGINNER, "   ")


def test_cohort_key_is_a_distinct_namespace() -> None:
    key = _key()
    scoped = cohort_scoped_key(key, COHORT)
    assert scoped.cohort_id == COHORT
    assert scoped.fingerprint() != key.fingerprint()
    # Same dimensions otherwise.
    assert scoped.role_target == key.role_target
    with pytest.raises(ValueError, match="non-empty"):
        cohort_scoped_key(key, "  ")


def test_consented_lookup_prefers_cohort_entry() -> None:
    cache = InMemoryCache()
    key = _key()
    cache.put(_entry(key, "global"))
    cache.put(_entry(cohort_scoped_key(key, COHORT), "cohort"))
    result = cohort_lookup(cache, key, cohort_id=COHORT)
    assert result.source is CohortLookupSource.COHORT
    assert result.entry is not None
    assert result.entry.value_json["marker"] == "cohort"


def test_consented_lookup_falls_back_to_global() -> None:
    cache = InMemoryCache()
    key = _key()
    cache.put(_entry(key, "global"))
    result = cohort_lookup(cache, key, cohort_id=COHORT)
    assert result.source is CohortLookupSource.GLOBAL
    assert result.entry is not None
    assert result.entry.value_json["marker"] == "global"


def test_unconsented_lookup_never_sees_cohort_entries() -> None:
    cache = InMemoryCache()
    key = _key()
    cache.put(_entry(cohort_scoped_key(key, COHORT), "cohort"))
    result = cohort_lookup(cache, key, cohort_id=None)
    assert result.source is CohortLookupSource.MISS
    assert result.entry is None


def test_lookup_rejects_pre_scoped_key() -> None:
    cache = InMemoryCache()
    with pytest.raises(ValueError, match="global key"):
        cohort_lookup(cache, cohort_scoped_key(_key(), COHORT), cohort_id=COHORT)


def _gate() -> tuple[ConsentGate, InMemoryConsentStore, InMemoryDataAccessAuditStore]:
    consents = InMemoryConsentStore(clock=FrozenClock(T0))
    audit = InMemoryDataAccessAuditStore()
    gate = ConsentGate(
        consents,
        audit,
        clock=FrozenClock(T0),
        id_generator=DeterministicIdGenerator(),
    )
    return gate, consents, audit


def _cohort_consent(user_id: str = "user_123") -> ConsentRecord:
    return ConsentRecord.model_validate(
        {
            "consent_record_id": "consent_cr_001",
            "user_id": user_id,
            "scope": ConsentScope.COHORT_RETRIEVAL,
            "status": "granted",
            "consent_version": "2026-06",
            "granted_at": T0,
            "created_at": T0,
            "updated_at": T0,
        }
    )


def test_cohort_path_blocked_without_consent_end_to_end() -> None:
    """Composition-root wiring: gate denial -> cohort_id None -> global only,
    with the denial audited."""
    gate, _, audit = _gate()
    cache = InMemoryCache()
    key = _key()
    cache.put(_entry(cohort_scoped_key(key, COHORT), "cohort"))

    decision = gate.check(
        "user_123", DataAccessPurpose.COHORT_RETRIEVAL, DataAccessor.RETRIEVAL_PIPELINE
    )
    assert decision.allowed is False
    cohort_id = COHORT if decision.allowed else None
    result = cohort_lookup(cache, key, cohort_id=cohort_id)
    assert result.source is CohortLookupSource.MISS
    assert audit.list_for_user("user_123")[0].reason_code is ReasonCode.CONSENT_MISSING


def test_cohort_path_opens_with_consent_and_closes_on_revoke() -> None:
    gate, consents, _ = _gate()
    cache = InMemoryCache()
    key = _key()
    cache.put(_entry(cohort_scoped_key(key, COHORT), "cohort"))
    consents.grant(_cohort_consent())

    allowed = gate.check(
        "user_123", DataAccessPurpose.COHORT_RETRIEVAL, DataAccessor.RETRIEVAL_PIPELINE
    )
    assert allowed.allowed is True
    assert (
        cohort_lookup(cache, key, cohort_id=COHORT).source is CohortLookupSource.COHORT
    )

    consents.revoke("consent_cr_001")
    denied = gate.check(
        "user_123", DataAccessPurpose.COHORT_RETRIEVAL, DataAccessor.RETRIEVAL_PIPELINE
    )
    assert denied.allowed is False
    assert denied.reason_code is ReasonCode.CONSENT_REVOKED
    # The composition root now passes None; cohort entries are unreachable.
    assert cohort_lookup(cache, key, cohort_id=None).source is CohortLookupSource.MISS
