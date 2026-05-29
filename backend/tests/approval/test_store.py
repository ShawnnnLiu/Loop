"""Tests for ``InMemoryApprovalEventStore`` (Phase 2)."""

from __future__ import annotations

import contextlib
import threading
from datetime import UTC, datetime, timedelta

import pytest

from agentic_calendar.approval.store import (
    ApprovalEventAlreadyExistsError,
    ApprovalEventNotFoundError,
    ApprovalEventStore,
    InMemoryApprovalEventStore,
)
from agentic_calendar.contracts.approval_event import (
    ApprovalActionType,
    ApprovalEvent,
    HashAlgorithm,
)

_HASH = "sha256:" + ("a" * 64)


def _event(
    *,
    approval_event_id: str = "approval_001",
    user_id: str = "user_a",
    draft_schedule_id: str = "draft_a",
    created_at: datetime = datetime(2026, 5, 4, 17, 55, tzinfo=UTC),
    expires_offset: timedelta = timedelta(hours=24),
) -> ApprovalEvent:
    return ApprovalEvent(
        approval_event_id=approval_event_id,
        user_id=user_id,
        plan_id="plan_a",
        draft_schedule_id=draft_schedule_id,
        action_type=ApprovalActionType.ADD_TO_CALENDAR,
        approved_payload_hash=_HASH,
        hash_algorithm=HashAlgorithm.SHA256,
        hash_canonicalization_version="v1",
        created_at=created_at,
        expires_at=created_at + expires_offset,
    )


def test_in_memory_store_satisfies_protocol() -> None:
    assert isinstance(InMemoryApprovalEventStore(), ApprovalEventStore)


def test_save_then_get() -> None:
    store = InMemoryApprovalEventStore()
    ev = _event()
    store.save(ev)
    assert store.get("approval_001") == ev


def test_get_missing_raises() -> None:
    store = InMemoryApprovalEventStore()
    with pytest.raises(ApprovalEventNotFoundError):
        store.get("nope")


def test_save_twice_with_same_id_rejected() -> None:
    """Spec line 95 immutability — approval events cannot be re-saved."""
    store = InMemoryApprovalEventStore()
    store.save(_event())
    with pytest.raises(ApprovalEventAlreadyExistsError):
        store.save(_event())


def test_save_twice_with_same_id_but_different_payload_rejected() -> None:
    store = InMemoryApprovalEventStore()
    store.save(_event())
    other = _event(user_id="user_DIFFERENT")
    with pytest.raises(ApprovalEventAlreadyExistsError):
        store.save(other)


def test_save_different_ids_coexist() -> None:
    store = InMemoryApprovalEventStore()
    store.save(_event(approval_event_id="a1"))
    store.save(_event(approval_event_id="a2"))
    assert store.get("a1").approval_event_id == "a1"
    assert store.get("a2").approval_event_id == "a2"


def test_list_for_user_filters_correctly() -> None:
    store = InMemoryApprovalEventStore()
    store.save(_event(approval_event_id="a1", user_id="alice"))
    store.save(_event(approval_event_id="a2", user_id="alice"))
    store.save(_event(approval_event_id="a3", user_id="bob"))
    alice_events = store.list_for_user("alice")
    assert {ev.approval_event_id for ev in alice_events} == {"a1", "a2"}
    assert store.list_for_user("bob")[0].approval_event_id == "a3"
    assert store.list_for_user("nobody") == []


def test_list_for_user_sorted_by_created_at() -> None:
    store = InMemoryApprovalEventStore()
    early = _event(
        approval_event_id="early",
        created_at=datetime(2026, 5, 4, 8, 0, tzinfo=UTC),
    )
    late = _event(
        approval_event_id="late",
        created_at=datetime(2026, 5, 4, 18, 0, tzinfo=UTC),
    )
    # Save out of order.
    store.save(late)
    store.save(early)
    listed = store.list_for_user("user_a")
    assert [ev.approval_event_id for ev in listed] == ["early", "late"]


def test_list_for_draft_filters_correctly() -> None:
    store = InMemoryApprovalEventStore()
    store.save(_event(approval_event_id="a1", draft_schedule_id="d1"))
    store.save(_event(approval_event_id="a2", draft_schedule_id="d1"))
    store.save(_event(approval_event_id="a3", draft_schedule_id="d2"))
    d1_events = store.list_for_draft("d1")
    assert {ev.approval_event_id for ev in d1_events} == {"a1", "a2"}
    assert store.list_for_draft("d2")[0].approval_event_id == "a3"
    assert store.list_for_draft("nothing") == []


def test_concurrent_saves_produce_no_torn_state() -> None:
    """Smoke test that the RLock keeps the bucket consistent under contention."""
    store = InMemoryApprovalEventStore()

    def saver(start: int) -> None:
        for i in range(start, start + 25):
            with contextlib.suppress(ApprovalEventAlreadyExistsError):
                store.save(_event(approval_event_id=f"a{i}"))

    threads = [
        threading.Thread(target=saver, args=(0,)),
        threading.Thread(target=saver, args=(0,)),
        threading.Thread(target=saver, args=(25,)),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    listed = store.list_for_user("user_a")
    assert {ev.approval_event_id for ev in listed} == {f"a{i}" for i in range(50)}
