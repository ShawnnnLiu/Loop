"""Tests for ``InMemoryConsentStore`` lifecycle enforcement (Phase 6a)."""

from __future__ import annotations

import threading

import pytest
from pydantic import ValidationError

from agentic_calendar.common.clock import FrozenClock
from agentic_calendar.consent.store import (
    ConsentAlreadyGrantedError,
    ConsentRecordAlreadyExistsError,
    ConsentRecordNotFoundError,
    ConsentStore,
    IllegalConsentTransitionError,
    InMemoryConsentStore,
    NonGrantedConsentInsertError,
)
from agentic_calendar.contracts.consent_record import (
    ConsentRecord,
    ConsentScope,
    ConsentStatus,
)

from ._builders import T0, build_consent_record


def _store() -> InMemoryConsentStore:
    return InMemoryConsentStore(clock=FrozenClock(T0))


def test_satisfies_protocol() -> None:
    assert isinstance(_store(), ConsentStore)


def test_grant_then_get() -> None:
    store = _store()
    store.grant(build_consent_record())
    assert store.get("consent_001").status is ConsentStatus.GRANTED


def test_grant_rejects_duplicate_id() -> None:
    store = _store()
    store.grant(build_consent_record())
    with pytest.raises(ConsentRecordAlreadyExistsError):
        store.grant(build_consent_record(scope=ConsentScope.COHORT_RETRIEVAL))


def test_grant_rejects_revoked_record() -> None:
    store = _store()
    revoked = build_consent_record(
        status=ConsentStatus.REVOKED, revoked_at=T0, updated_at=T0
    )
    with pytest.raises(NonGrantedConsentInsertError):
        store.grant(revoked)


def test_grant_rejects_second_active_grant_for_same_scope() -> None:
    store = _store()
    store.grant(build_consent_record())
    with pytest.raises(ConsentAlreadyGrantedError):
        store.grant(build_consent_record(consent_record_id="consent_002"))


def test_same_user_may_hold_both_scopes() -> None:
    store = _store()
    store.grant(build_consent_record())
    store.grant(
        build_consent_record(
            consent_record_id="consent_002", scope=ConsentScope.COHORT_RETRIEVAL
        )
    )
    assert len(store.list_for_user("user_123")) == 2


def test_get_missing_raises() -> None:
    with pytest.raises(ConsentRecordNotFoundError):
        _store().get("nope")


def test_revoke_sets_status_and_timestamps() -> None:
    store = _store()
    store.grant(build_consent_record())
    revoked = store.revoke("consent_001")
    assert revoked.status is ConsentStatus.REVOKED
    assert revoked.revoked_at == T0
    assert revoked.updated_at == T0
    assert revoked.is_active() is False
    # The stored row reflects the revocation for the next reader.
    assert store.get("consent_001").status is ConsentStatus.REVOKED


def test_revoke_of_revoked_record_is_illegal() -> None:
    store = _store()
    store.grant(build_consent_record())
    store.revoke("consent_001")
    with pytest.raises(IllegalConsentTransitionError) as exc:
        store.revoke("consent_001")
    assert exc.value.current is ConsentStatus.REVOKED
    assert exc.value.requested is ConsentStatus.REVOKED


def test_regrant_after_revoke_is_a_new_record() -> None:
    store = _store()
    store.grant(build_consent_record())
    store.revoke("consent_001")
    store.grant(build_consent_record(consent_record_id="consent_002"))
    active = store.get_active("user_123", ConsentScope.POOLED_TRAINING)
    assert active is not None
    assert active.consent_record_id == "consent_002"
    # History keeps both rows.
    assert [r.consent_record_id for r in store.list_for_user("user_123")] == [
        "consent_001",
        "consent_002",
    ]


def test_get_active_none_when_revoked_or_absent() -> None:
    store = _store()
    assert store.get_active("user_123", ConsentScope.POOLED_TRAINING) is None
    store.grant(build_consent_record())
    store.revoke("consent_001")
    assert store.get_active("user_123", ConsentScope.POOLED_TRAINING) is None


def test_latest_for_scope_distinguishes_missing_from_revoked() -> None:
    store = _store()
    assert store.latest_for_scope("user_123", ConsentScope.POOLED_TRAINING) is None
    store.grant(build_consent_record())
    store.revoke("consent_001")
    latest = store.latest_for_scope("user_123", ConsentScope.POOLED_TRAINING)
    assert latest is not None
    assert latest.status is ConsentStatus.REVOKED


def test_load_rehydrates_revoked_history() -> None:
    store = _store()
    store.load(
        build_consent_record(status=ConsentStatus.REVOKED, revoked_at=T0, updated_at=T0)
    )
    assert store.get("consent_001").status is ConsentStatus.REVOKED


def test_load_enforces_single_active_grant() -> None:
    store = _store()
    store.load(build_consent_record())
    with pytest.raises(ConsentAlreadyGrantedError):
        store.load(build_consent_record(consent_record_id="consent_002"))


def test_delete_for_user_removes_only_that_user() -> None:
    store = _store()
    store.grant(build_consent_record())
    store.grant(build_consent_record(consent_record_id="consent_002", user_id="user_456"))
    assert store.delete_for_user("user_123") == 1
    assert store.list_for_user("user_123") == []
    assert len(store.list_for_user("user_456")) == 1
    # Deleting again is a no-op with an honest zero count.
    assert store.delete_for_user("user_123") == 0


def test_returned_record_is_frozen() -> None:
    store = _store()
    store.grant(build_consent_record())
    revoked = store.revoke("consent_001")
    with pytest.raises(ValidationError):
        revoked.status = ConsentStatus.GRANTED  # type: ignore[misc]


def test_revoke_replaces_stored_row_without_mutating_prior() -> None:
    store = _store()
    store.grant(build_consent_record())
    before = store.get("consent_001")
    after = store.revoke("consent_001")
    # A new immutable instance is stored; the previously-read row is unchanged.
    assert before.status is ConsentStatus.GRANTED
    assert after is not before
    assert store.get("consent_001") is after


def test_concurrent_revoke_serializes_to_one_winner() -> None:
    store = _store()
    store.grant(build_consent_record())

    successes: list[ConsentRecord] = []
    illegal = 0
    lock = threading.Lock()

    def worker() -> None:
        nonlocal illegal
        try:
            result = store.revoke("consent_001")
        except IllegalConsentTransitionError:
            with lock:
                illegal += 1
        else:
            with lock:
                successes.append(result)

    threads = [threading.Thread(target=worker) for _ in range(16)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # The lock makes the transition atomic: exactly one revoke wins.
    assert len(successes) == 1
    assert illegal == 15
    assert store.get("consent_001").status is ConsentStatus.REVOKED


def test_concurrent_grants_for_same_scope_admit_exactly_one() -> None:
    store = _store()

    granted = 0
    rejected = 0
    lock = threading.Lock()

    def worker(i: int) -> None:
        nonlocal granted, rejected
        try:
            store.grant(build_consent_record(consent_record_id=f"consent_{i:03d}"))
        except ConsentAlreadyGrantedError:
            with lock:
                rejected += 1
        else:
            with lock:
                granted += 1

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(16)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert granted == 1
    assert rejected == 15
    assert store.get_active("user_123", ConsentScope.POOLED_TRAINING) is not None
