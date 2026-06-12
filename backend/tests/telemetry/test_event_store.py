"""Tests for the ``TelemetryEventStore`` implementations.

The behavioral suite is parametrized over the in-memory and SQLite
implementations (Phase 9a): both must satisfy the protocol identically.
The restart-survival test at the bottom is SQLite-only by nature.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from agentic_calendar.common.sqlite import SqliteDatabase
from agentic_calendar.contracts.telemetry import TelemetryEvent
from agentic_calendar.telemetry.event_store import (
    InMemoryTelemetryEventStore,
    TelemetryEventAlreadyExistsError,
    TelemetryEventStore,
)
from agentic_calendar.telemetry.sqlite_event_store import SqliteTelemetryEventStore
from tests._fixture_loader import iter_valid


@pytest.fixture(params=["in_memory", "sqlite"])
def store(request: pytest.FixtureRequest, tmp_path: Path) -> TelemetryEventStore:
    if request.param == "sqlite":
        return SqliteTelemetryEventStore(SqliteDatabase(tmp_path / "store.db"))
    return InMemoryTelemetryEventStore()


def _make_event(event_id: str, task_id: str = "dp_002") -> TelemetryEvent:
    base = TelemetryEvent.model_validate(next(iter_valid("telemetry")).payload)
    return base.model_copy(update={"telemetry_event_id": event_id, "task_id": task_id})


def test_satisfies_protocol(store: TelemetryEventStore) -> None:
    assert isinstance(store, TelemetryEventStore)


def test_append_and_get_round_trip(store: TelemetryEventStore) -> None:
    event = _make_event("tel_001")
    store.append(event)
    assert store.get("tel_001") == event


def test_append_rejects_duplicate_id(store: TelemetryEventStore) -> None:
    event = _make_event("tel_001")
    store.append(event)
    with pytest.raises(TelemetryEventAlreadyExistsError):
        store.append(event)
    assert len(store.all()) == 1


def test_exists(store: TelemetryEventStore) -> None:
    store.append(_make_event("tel_001"))
    assert store.exists("tel_001")
    assert not store.exists("tel_missing")


def test_get_missing_returns_none(store: TelemetryEventStore) -> None:
    assert store.get("tel_missing") is None


def test_list_for_task_filters_and_preserves_insertion_order(
    store: TelemetryEventStore,
) -> None:
    a = _make_event("tel_a", task_id="task_1")
    b = _make_event("tel_b", task_id="task_2")
    c = _make_event("tel_c", task_id="task_1")
    store.append(a)
    store.append(b)
    store.append(c)
    assert store.list_for_task("task_1") == [a, c]
    assert store.list_for_task("task_2") == [b]
    assert store.list_for_task("task_missing") == []


def test_all_preserves_insertion_order(store: TelemetryEventStore) -> None:
    events = [_make_event(f"tel_{i:03d}", task_id=f"task_{i % 2}") for i in range(5)]
    for event in events:
        store.append(event)
    assert store.all() == events


def test_delete_for_tasks_removes_matching_and_returns_count(
    store: TelemetryEventStore,
) -> None:
    """Multi-task delete: only the named tasks' events go; survivors keep order."""
    a = _make_event("tel_a", task_id="task_1")
    b = _make_event("tel_b", task_id="task_2")
    c = _make_event("tel_c", task_id="task_1")
    d = _make_event("tel_d", task_id="task_3")
    e = _make_event("tel_e", task_id="task_2")
    for event in (a, b, c, d, e):
        store.append(event)

    removed = store.delete_for_tasks({"task_1", "task_3"})

    assert removed == 3
    assert not store.exists("tel_a")
    assert store.get("tel_c") is None
    assert store.list_for_task("task_1") == []
    # Survivors are intact and still in insertion order.
    assert store.all() == [b, e]
    assert store.list_for_task("task_2") == [b, e]


def test_delete_for_tasks_with_no_matches_returns_zero(
    store: TelemetryEventStore,
) -> None:
    event = _make_event("tel_001", task_id="task_1")
    store.append(event)
    assert store.delete_for_tasks({"task_missing"}) == 0
    assert store.delete_for_tasks(set()) == 0
    assert store.all() == [event]


# --------------------------------------------------------------------------- #
# Restart survival (SQLite-only by nature): state written before a process
# exit must be fully recovered by a fresh store instance on the same file.
# --------------------------------------------------------------------------- #


def test_sqlite_state_survives_restart(tmp_path: Path) -> None:
    db_path = tmp_path / "store.db"
    db = SqliteDatabase(db_path)
    first = SqliteTelemetryEventStore(db)
    a = _make_event("tel_a", task_id="task_1")
    b = _make_event("tel_b", task_id="task_2")
    first.append(a)
    first.append(b)
    db.close()

    reopened = SqliteTelemetryEventStore(SqliteDatabase(db_path))
    assert reopened.all() == [a, b]
    assert reopened.list_for_task("task_1") == [a]
    assert reopened.exists("tel_b")
    assert reopened.get("tel_a") == a
