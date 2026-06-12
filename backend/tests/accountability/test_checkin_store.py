"""Tests for the append-only check-in event store.

The behavioral suite is parametrized over the in-memory and SQLite
implementations (Phase 9a): both must satisfy the protocol identically.
The restart-survival test at the bottom is SQLite-only by nature.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from agentic_calendar.accountability.checkin_store import (
    CheckinEventAlreadyExistsError,
    CheckinEventStore,
    InMemoryCheckinEventStore,
)
from agentic_calendar.accountability.sqlite_checkin_store import SqliteCheckinEventStore
from agentic_calendar.common.sqlite import SqliteDatabase

from ._builders import build_checkin_event


@pytest.fixture(params=["in_memory", "sqlite"])
def store(request: pytest.FixtureRequest, tmp_path: Path) -> CheckinEventStore:
    if request.param == "sqlite":
        return SqliteCheckinEventStore(SqliteDatabase(tmp_path / "store.db"))
    return InMemoryCheckinEventStore()


def test_satisfies_protocol(store: CheckinEventStore) -> None:
    assert isinstance(store, CheckinEventStore)


def test_append_and_read_back(store: CheckinEventStore) -> None:
    event = build_checkin_event()
    store.append(event)
    assert store.exists("checkin_1")
    assert store.get("checkin_1") == event
    assert store.all() == [event]


def test_get_missing_returns_none(store: CheckinEventStore) -> None:
    assert store.get("missing") is None


def test_append_only_rejects_duplicate_id(store: CheckinEventStore) -> None:
    store.append(build_checkin_event())
    with pytest.raises(CheckinEventAlreadyExistsError):
        store.append(build_checkin_event())


def test_list_for_plan_scopes_by_user_and_plan(store: CheckinEventStore) -> None:
    mine = build_checkin_event(checkin_id="checkin_a")
    other_user = build_checkin_event(checkin_id="checkin_b", user_id="user_999")
    other_plan = build_checkin_event(checkin_id="checkin_c", plan_id="plan_999")
    for e in (mine, other_user, other_plan):
        store.append(e)
    assert store.list_for_plan("user_123", "plan_004") == [mine]


def test_insertion_order_preserved(store: CheckinEventStore) -> None:
    first = build_checkin_event(checkin_id="checkin_first")
    second = build_checkin_event(checkin_id="checkin_second")
    store.append(first)
    store.append(second)
    assert [e.checkin_id for e in store.all()] == ["checkin_first", "checkin_second"]


# --------------------------------------------------------------------------- #
# Restart survival (SQLite-only by nature): state written before a process
# exit must be fully recovered by a fresh store instance on the same file.
# --------------------------------------------------------------------------- #


def test_sqlite_state_survives_restart(tmp_path: Path) -> None:
    db_path = tmp_path / "store.db"
    db = SqliteDatabase(db_path)
    first = SqliteCheckinEventStore(db)
    mine = build_checkin_event(checkin_id="checkin_a")
    other_user = build_checkin_event(checkin_id="checkin_b", user_id="user_999")
    first.append(mine)
    first.append(other_user)
    db.close()

    reopened = SqliteCheckinEventStore(SqliteDatabase(db_path))
    assert reopened.exists("checkin_a")
    assert reopened.get("checkin_a") == mine
    assert reopened.list_for_plan("user_123", "plan_004") == [mine]
    assert reopened.all() == [mine, other_user]
