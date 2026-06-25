"""Tests for the ``TaskDispositionStore`` implementations.

Parametrized over the in-memory and SQLite implementations: both must satisfy
the protocol identically. The restart-survival test at the bottom is
SQLite-only by nature.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from agentic_calendar.common.sqlite import SqliteDatabase
from agentic_calendar.contracts.reason_codes import ReasonCode
from agentic_calendar.contracts.task_disposition import (
    DispositionSource,
    TaskDispositionRecord,
    TaskDispositionType,
)
from agentic_calendar.disposition.disposition_store import (
    InMemoryTaskDispositionStore,
    TaskDispositionAlreadyExistsError,
    TaskDispositionStore,
)
from agentic_calendar.disposition.sqlite_disposition_store import (
    SqliteTaskDispositionStore,
)

_NOW = datetime(2026, 6, 24, 19, 0, tzinfo=UTC)


@pytest.fixture(params=["in_memory", "sqlite"])
def store(request: pytest.FixtureRequest, tmp_path: Path) -> TaskDispositionStore:
    if request.param == "sqlite":
        return SqliteTaskDispositionStore(SqliteDatabase(tmp_path / "disp.db"))
    return InMemoryTaskDispositionStore()


def _completed(
    disposition_id: str,
    task_id: str,
    *,
    user_id: str = "user_1",
    plan_version: str = "plan_1",
) -> TaskDispositionRecord:
    return TaskDispositionRecord(
        disposition_id=disposition_id,
        user_id=user_id,
        plan_version=plan_version,
        task_id=task_id,
        disposition=TaskDispositionType.COMPLETED,
        reason_code=None,
        source=DispositionSource.SYSTEM,
        created_at=_NOW,
    )


def _dropped(
    disposition_id: str,
    task_id: str,
    *,
    user_id: str = "user_1",
    plan_version: str = "plan_1",
) -> TaskDispositionRecord:
    return TaskDispositionRecord(
        disposition_id=disposition_id,
        user_id=user_id,
        plan_version=plan_version,
        task_id=task_id,
        disposition=TaskDispositionType.DROPPED,
        reason_code=ReasonCode.TASK_DROPPED_BY_USER,
        source=DispositionSource.USER,
        created_at=_NOW,
    )


def test_satisfies_protocol(store: TaskDispositionStore) -> None:
    assert isinstance(store, TaskDispositionStore)


def test_append_and_list_for_user(store: TaskDispositionStore) -> None:
    a = _completed("d1", "t1")
    b = _dropped("d2", "t2")
    store.append(a)
    store.append(b)
    assert store.list_for_user("user_1") == [a, b]
    assert store.list_for_user("nobody") == []


def test_append_rejects_duplicate_id(store: TaskDispositionStore) -> None:
    store.append(_completed("d1", "t1"))
    with pytest.raises(TaskDispositionAlreadyExistsError):
        store.append(_completed("d1", "t_other"))
    assert len(store.list_for_user("user_1")) == 1


def test_exists(store: TaskDispositionStore) -> None:
    store.append(_completed("d1", "t1"))
    assert store.exists("d1")
    assert not store.exists("missing")


def test_list_for_plan_filters_by_plan_version(store: TaskDispositionStore) -> None:
    store.append(_completed("d1", "t1", plan_version="plan_1"))
    store.append(_completed("d2", "t2", plan_version="plan_2"))
    rows = store.list_for_plan("user_1", "plan_2")
    assert [r.task_id for r in rows] == ["t2"]


def test_task_ids_with_disposition_unions_across_plan_versions(
    store: TaskDispositionStore,
) -> None:
    store.append(_completed("d1", "t1", plan_version="plan_1"))
    store.append(_completed("d2", "t2", plan_version="plan_2"))
    store.append(_dropped("d3", "t3", plan_version="plan_2"))
    assert store.task_ids_with_disposition("user_1", TaskDispositionType.COMPLETED) == {
        "t1",
        "t2",
    }
    assert store.task_ids_with_disposition("user_1", TaskDispositionType.DROPPED) == {
        "t3"
    }
    assert (
        store.task_ids_with_disposition("user_1", TaskDispositionType.SKIPPED) == set()
    )


def test_task_ids_with_disposition_scoped_by_user(store: TaskDispositionStore) -> None:
    store.append(_completed("d1", "t1", user_id="user_1"))
    store.append(_completed("d2", "t2", user_id="user_2"))
    assert store.task_ids_with_disposition("user_1", TaskDispositionType.COMPLETED) == {
        "t1"
    }


def test_delete_for_user_removes_and_counts(store: TaskDispositionStore) -> None:
    store.append(_completed("d1", "t1", user_id="user_1"))
    store.append(_dropped("d2", "t2", user_id="user_1"))
    store.append(_completed("d3", "t3", user_id="user_2"))
    removed = store.delete_for_user("user_1")
    assert removed == 2
    assert store.list_for_user("user_1") == []
    assert not store.exists("d1")
    # other users are untouched
    assert [r.task_id for r in store.list_for_user("user_2")] == ["t3"]


def test_sqlite_state_survives_restart(tmp_path: Path) -> None:
    db_path = tmp_path / "disp.db"
    db = SqliteDatabase(db_path)
    first = SqliteTaskDispositionStore(db)
    a = _completed("d1", "t1")
    b = _dropped("d2", "t2")
    first.append(a)
    first.append(b)
    db.close()

    reopened = SqliteTaskDispositionStore(SqliteDatabase(db_path))
    assert reopened.list_for_user("user_1") == [a, b]
    assert reopened.exists("d1")
    assert reopened.task_ids_with_disposition(
        "user_1", TaskDispositionType.DROPPED
    ) == {"t2"}
