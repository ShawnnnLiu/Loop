"""Tests for the append-only check-in event store."""

from __future__ import annotations

import pytest

from agentic_calendar.accountability.checkin_store import (
    CheckinEventAlreadyExistsError,
    InMemoryCheckinEventStore,
)

from ._builders import build_checkin_event


def test_append_and_read_back() -> None:
    store = InMemoryCheckinEventStore()
    event = build_checkin_event()
    store.append(event)
    assert store.exists("checkin_1")
    assert store.get("checkin_1") == event
    assert store.all() == [event]


def test_append_only_rejects_duplicate_id() -> None:
    store = InMemoryCheckinEventStore()
    store.append(build_checkin_event())
    with pytest.raises(CheckinEventAlreadyExistsError):
        store.append(build_checkin_event())


def test_list_for_plan_scopes_by_user_and_plan() -> None:
    store = InMemoryCheckinEventStore()
    mine = build_checkin_event(checkin_id="checkin_a")
    other_user = build_checkin_event(checkin_id="checkin_b", user_id="user_999")
    other_plan = build_checkin_event(checkin_id="checkin_c", plan_id="plan_999")
    for e in (mine, other_user, other_plan):
        store.append(e)
    assert store.list_for_plan("user_123", "plan_004") == [mine]


def test_insertion_order_preserved() -> None:
    store = InMemoryCheckinEventStore()
    first = build_checkin_event(checkin_id="checkin_first")
    second = build_checkin_event(checkin_id="checkin_second")
    store.append(first)
    store.append(second)
    assert [e.checkin_id for e in store.all()] == ["checkin_first", "checkin_second"]
