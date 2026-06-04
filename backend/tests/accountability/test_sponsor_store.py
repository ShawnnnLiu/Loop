"""Tests for ``InMemorySponsorStore`` invite-lifecycle enforcement (Phase 3)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from agentic_calendar.accountability.sponsor_store import (
    IllegalSponsorTransitionError,
    InMemorySponsorStore,
    SponsorAlreadyExistsError,
    SponsorNotFoundError,
    SponsorStore,
)
from agentic_calendar.common.clock import FrozenClock
from agentic_calendar.contracts.sponsor import Sponsor, SponsorStatus

from ._builders import T0, build_sponsor


def _store() -> InMemorySponsorStore:
    return InMemorySponsorStore(clock=FrozenClock(T0))


def test_satisfies_protocol() -> None:
    assert isinstance(_store(), SponsorStore)


def test_invite_then_get() -> None:
    store = _store()
    pending = build_sponsor(status=SponsorStatus.PENDING, accepted_at=None, revoked_at=None)
    store.invite(pending)
    assert store.get("sponsor_001").status is SponsorStatus.PENDING


def test_invite_rejects_duplicate() -> None:
    store = _store()
    store.invite(build_sponsor(status=SponsorStatus.PENDING, accepted_at=None))
    with pytest.raises(SponsorAlreadyExistsError):
        store.invite(build_sponsor(status=SponsorStatus.PENDING, accepted_at=None))


def test_get_missing_raises() -> None:
    with pytest.raises(SponsorNotFoundError):
        _store().get("nope")


def test_accept_sets_status_and_timestamp() -> None:
    store = _store()
    store.invite(build_sponsor(status=SponsorStatus.PENDING, accepted_at=None))
    accepted = store.accept("sponsor_001")
    assert accepted.status is SponsorStatus.ACCEPTED
    assert accepted.accepted_at == T0
    assert accepted.revoked_at is None
    assert accepted.is_reportable() is True


def test_revoke_from_pending() -> None:
    store = _store()
    store.invite(build_sponsor(status=SponsorStatus.PENDING, accepted_at=None))
    revoked = store.revoke("sponsor_001")
    assert revoked.status is SponsorStatus.REVOKED
    assert revoked.revoked_at == T0
    assert revoked.is_reportable() is False


def test_revoke_from_accepted_takes_effect_immediately() -> None:
    store = _store()
    store.invite(build_sponsor(status=SponsorStatus.PENDING, accepted_at=None))
    store.accept("sponsor_001")
    revoked = store.revoke("sponsor_001")
    assert revoked.status is SponsorStatus.REVOKED
    # The stored row reflects the revocation for the next reader.
    assert store.get("sponsor_001").status is SponsorStatus.REVOKED


def test_cannot_accept_revoked_sponsor() -> None:
    store = _store()
    store.invite(build_sponsor(status=SponsorStatus.PENDING, accepted_at=None))
    store.revoke("sponsor_001")
    with pytest.raises(IllegalSponsorTransitionError) as exc:
        store.accept("sponsor_001")
    assert exc.value.current is SponsorStatus.REVOKED
    assert exc.value.requested is SponsorStatus.ACCEPTED


def test_cannot_re_accept_accepted_sponsor() -> None:
    store = _store()
    store.invite(build_sponsor(status=SponsorStatus.PENDING, accepted_at=None))
    store.accept("sponsor_001")
    with pytest.raises(IllegalSponsorTransitionError):
        store.accept("sponsor_001")


def test_list_for_user_sorted_by_invited_at() -> None:
    store = _store()
    store.invite(
        build_sponsor(sponsor_id="sponsor_001", status=SponsorStatus.PENDING, accepted_at=None)
    )
    store.invite(
        build_sponsor(sponsor_id="sponsor_002", status=SponsorStatus.PENDING, accepted_at=None)
    )
    rows = store.list_for_user("user_123")
    assert [r.sponsor_id for r in rows] == ["sponsor_001", "sponsor_002"]
    assert store.list_for_user("someone_else") == []


def _seed(store: InMemorySponsorStore, status: SponsorStatus) -> None:
    """Insert a sponsor already in ``status`` (bypassing the transition path)."""
    if status is SponsorStatus.PENDING:
        store.invite(build_sponsor(status=status, accepted_at=None, revoked_at=None))
    elif status is SponsorStatus.ACCEPTED:
        store.invite(build_sponsor(status=status, accepted_at=T0, revoked_at=None))
    else:  # REVOKED
        store.invite(build_sponsor(status=status, accepted_at=None, revoked_at=T0))


# (from_status, action, legal, resulting_status)
_TRANSITIONS = [
    (SponsorStatus.PENDING, "accept", True, SponsorStatus.ACCEPTED),
    (SponsorStatus.PENDING, "revoke", True, SponsorStatus.REVOKED),
    (SponsorStatus.ACCEPTED, "accept", False, None),
    (SponsorStatus.ACCEPTED, "revoke", True, SponsorStatus.REVOKED),
    (SponsorStatus.REVOKED, "accept", False, None),
    (SponsorStatus.REVOKED, "revoke", False, None),
]


@pytest.mark.parametrize(
    ("from_status", "action", "legal", "resulting"),
    _TRANSITIONS,
    ids=[f"{f.value}-{a}" for f, a, _, _ in _TRANSITIONS],
)
def test_transition_matrix(
    from_status: SponsorStatus,
    action: str,
    legal: bool,
    resulting: SponsorStatus | None,
) -> None:
    store = _store()
    _seed(store, from_status)
    call = store.accept if action == "accept" else store.revoke
    if legal:
        result = call("sponsor_001")
        assert result.status is resulting
    else:
        with pytest.raises(IllegalSponsorTransitionError) as exc:
            call("sponsor_001")
        assert exc.value.current is from_status


def test_returned_sponsor_is_frozen() -> None:
    store = _store()
    store.invite(build_sponsor(status=SponsorStatus.PENDING, accepted_at=None))
    accepted = store.accept("sponsor_001")
    with pytest.raises(ValidationError):
        accepted.status = SponsorStatus.REVOKED  # type: ignore[misc]


def test_transition_replaces_stored_row_without_mutating_prior() -> None:
    store = _store()
    store.invite(build_sponsor(status=SponsorStatus.PENDING, accepted_at=None))
    before = store.get("sponsor_001")
    after = store.accept("sponsor_001")
    # A new immutable instance is stored; the previously-read row is unchanged.
    assert before.status is SponsorStatus.PENDING
    assert after is not before
    assert store.get("sponsor_001") is after


def test_concurrent_accept_of_same_sponsor_serializes_to_one_winner() -> None:
    import threading

    store = _store()
    store.invite(build_sponsor(status=SponsorStatus.PENDING, accepted_at=None))

    successes: list[Sponsor] = []
    illegal = 0
    lock = threading.Lock()

    def worker() -> None:
        nonlocal illegal
        try:
            result = store.accept("sponsor_001")
        except IllegalSponsorTransitionError:
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

    # The lock makes the transition atomic: exactly one accept wins.
    assert len(successes) == 1
    assert illegal == 15
    assert store.get("sponsor_001").status is SponsorStatus.ACCEPTED


def test_concurrent_accept_of_distinct_sponsors_all_succeed() -> None:
    import threading

    store = _store()
    ids = [f"sponsor_{i:03d}" for i in range(50)]
    for sid in ids:
        store.invite(build_sponsor(sponsor_id=sid, status=SponsorStatus.PENDING, accepted_at=None))

    errors: list[Exception] = []

    def worker(sid: str) -> None:
        try:
            store.accept(sid)
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(sid,)) for sid in ids]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    assert all(store.get(sid).status is SponsorStatus.ACCEPTED for sid in ids)
