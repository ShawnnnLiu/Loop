"""Tests for the ``RecommitmentStore`` implementations (append-only, answer-once).

The behavioral suite is parametrized over the in-memory and SQLite
implementations (Phase 9a): both must satisfy the protocol identically. The
request/answer flow functions are covered in ``test_recommitment.py``; this
suite pins the store contract alone. Restart-survival tests at the bottom are
SQLite-only by nature.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from agentic_calendar.accountability.recommitment import (
    InMemoryRecommitmentStore,
    RecommitmentAlreadyAnsweredError,
    RecommitmentRequestAlreadyExistsError,
    RecommitmentRequestNotFoundError,
    RecommitmentStore,
)
from agentic_calendar.accountability.sqlite_recommitment_store import (
    SqliteRecommitmentStore,
)
from agentic_calendar.common.sqlite import SqliteDatabase
from agentic_calendar.contracts.reason_codes import ReasonCode
from agentic_calendar.contracts.recommitment import (
    RecommitmentChoice,
    RecommitmentEvent,
    RecommitmentRequest,
)

T = datetime(2026, 5, 10, 20, 0, tzinfo=UTC)


@pytest.fixture(params=["in_memory", "sqlite"])
def store(request: pytest.FixtureRequest, tmp_path: Path) -> RecommitmentStore:
    if request.param == "sqlite":
        return SqliteRecommitmentStore(SqliteDatabase(tmp_path / "store.db"))
    return InMemoryRecommitmentStore()


def _request(request_id: str = "recommit_req_1") -> RecommitmentRequest:
    return RecommitmentRequest(
        recommitment_request_id=request_id,
        user_id="user_123",
        plan_version="plan_004",
        decision_id="intv_1",
        reason_code=ReasonCode.USER_RECOMMITMENT_REQUIRED,
        requested_at=T,
    )


def _event(
    request_id: str = "recommit_req_1",
    *,
    event_id: str = "recommit_evt_1",
    choice: RecommitmentChoice = RecommitmentChoice.KEEP_PLAN,
) -> RecommitmentEvent:
    return RecommitmentEvent(
        recommitment_event_id=event_id,
        recommitment_request_id=request_id,
        user_id="user_123",
        plan_version="plan_004",
        choice=choice,
        created_at=T,
    )


def test_satisfies_protocol(store: RecommitmentStore) -> None:
    assert isinstance(store, RecommitmentStore)


def test_append_request_and_get_round_trip(store: RecommitmentStore) -> None:
    request = _request()
    store.append_request(request)
    assert store.get_request("recommit_req_1") == request


def test_append_request_rejects_duplicate(store: RecommitmentStore) -> None:
    store.append_request(_request())
    with pytest.raises(RecommitmentRequestAlreadyExistsError):
        store.append_request(_request())


def test_append_event_and_event_for_request_round_trip(store: RecommitmentStore) -> None:
    store.append_request(_request())
    event = _event()
    store.append_event(event)
    assert store.event_for_request("recommit_req_1") == event


def test_event_for_unknown_request_raises(store: RecommitmentStore) -> None:
    with pytest.raises(RecommitmentRequestNotFoundError):
        store.append_event(_event("recommit_req_unknown"))


def test_second_event_for_same_request_raises(store: RecommitmentStore) -> None:
    """Answer-once: a request may be answered at most once; the first stands."""
    store.append_request(_request())
    store.append_event(_event())
    with pytest.raises(RecommitmentAlreadyAnsweredError):
        store.append_event(
            _event(event_id="recommit_evt_2", choice=RecommitmentChoice.REVISE_TIMELINE)
        )
    first = store.event_for_request("recommit_req_1")
    assert first is not None
    assert first.choice is RecommitmentChoice.KEEP_PLAN


def test_get_request_returns_none_when_missing(store: RecommitmentStore) -> None:
    assert store.get_request("recommit_req_missing") is None


def test_event_for_request_returns_none_when_missing(store: RecommitmentStore) -> None:
    store.append_request(_request())
    assert store.event_for_request("recommit_req_1") is None


def test_all_requests_in_insertion_order(store: RecommitmentStore) -> None:
    requests = [_request(f"recommit_req_{i}") for i in (1, 2, 3)]
    for request in requests:
        store.append_request(request)
    assert store.all_requests() == requests


def test_all_events_in_insertion_order(store: RecommitmentStore) -> None:
    events = []
    for i in (1, 2, 3):
        store.append_request(_request(f"recommit_req_{i}"))
        events.append(_event(f"recommit_req_{i}", event_id=f"recommit_evt_{i}"))
    for event in events:
        store.append_event(event)
    assert store.all_events() == events


# --------------------------------------------------------------------------- #
# Restart survival (SQLite-only by nature): state written before a process
# exit must be fully recovered by a fresh store instance on the same file.
# --------------------------------------------------------------------------- #


def test_sqlite_state_survives_restart(tmp_path: Path) -> None:
    db_path = tmp_path / "store.db"
    db = SqliteDatabase(db_path)
    first = SqliteRecommitmentStore(db)
    answered = _request("recommit_req_1")
    unanswered = _request("recommit_req_2")
    answer = _event("recommit_req_1")
    first.append_request(answered)
    first.append_request(unanswered)
    first.append_event(answer)
    db.close()

    reopened = SqliteRecommitmentStore(SqliteDatabase(db_path))
    assert reopened.all_requests() == [answered, unanswered]
    assert reopened.all_events() == [answer]
    assert reopened.event_for_request("recommit_req_1") == answer
    assert reopened.event_for_request("recommit_req_2") is None
    # The answer-once invariant survives the restart.
    with pytest.raises(RecommitmentAlreadyAnsweredError):
        reopened.append_event(_event("recommit_req_1", event_id="recommit_evt_2"))
