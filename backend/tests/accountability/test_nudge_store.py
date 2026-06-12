"""Tests for the ``NudgeStore`` implementations.

The behavioral suite is parametrized over the in-memory and SQLite
implementations (Phase 9a): both must satisfy the protocol identically.
Nudge-engine behavior (trigger evaluation, quiet-hours deferral, audit
linkage) is covered in ``test_nudges.py``; this suite pins only the store
protocol. The restart-survival test at the bottom is SQLite-only by nature.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from agentic_calendar.accountability.nudge_store import (
    InMemoryNudgeStore,
    NudgeAlreadyExistsError,
    NudgeStore,
)
from agentic_calendar.accountability.sqlite_nudge_store import SqliteNudgeStore
from agentic_calendar.common.sqlite import SqliteDatabase
from agentic_calendar.contracts.motivation_profile import NudgeChannel
from agentic_calendar.contracts.nudge import NudgeRecord, NudgeStatus, NudgeToneTier
from agentic_calendar.contracts.reason_codes import ReasonCode

_CREATED_AT = datetime(2026, 5, 10, 19, 0, 0, tzinfo=UTC)


def _record(**overrides: Any) -> NudgeRecord:
    """Return a valid SENT ``NudgeRecord`` with sensible defaults."""
    defaults: dict[str, Any] = {
        "nudge_id": "nudge_1",
        "user_id": "user_123",
        "plan_id": "plan_004",
        "decision_id": "dec_1",
        "reason_code": ReasonCode.CHECKIN_DUE,
        "channel": NudgeChannel.IN_APP,
        "tone_tier": NudgeToneTier.STANDARD,
        "status": NudgeStatus.SENT,
        "recommitment_requested": False,
        "created_at": _CREATED_AT,
        "deliver_at": _CREATED_AT,
    }
    defaults.update(overrides)
    return NudgeRecord(**defaults)


@pytest.fixture(params=["in_memory", "sqlite"])
def store(request: pytest.FixtureRequest, tmp_path: Path) -> NudgeStore:
    if request.param == "sqlite":
        return SqliteNudgeStore(SqliteDatabase(tmp_path / "store.db"))
    return InMemoryNudgeStore()


def test_satisfies_protocol(store: NudgeStore) -> None:
    assert isinstance(store, NudgeStore)


def test_append_and_get_round_trip(store: NudgeStore) -> None:
    record = _record()
    store.append(record)
    assert store.get("nudge_1") == record
    assert store.all() == [record]


def test_append_only_rejects_duplicate_id(store: NudgeStore) -> None:
    store.append(_record())
    with pytest.raises(NudgeAlreadyExistsError):
        store.append(_record())


def test_get_missing_returns_none(store: NudgeStore) -> None:
    assert store.get("missing") is None


def test_list_for_user_filters_and_preserves_order(store: NudgeStore) -> None:
    mine_first = _record(nudge_id="nudge_a")
    other_user = _record(nudge_id="nudge_b", user_id="user_999")
    mine_second = _record(nudge_id="nudge_c")
    for record in (mine_first, other_user, mine_second):
        store.append(record)
    assert store.list_for_user("user_123") == [mine_first, mine_second]


def test_all_preserves_insertion_order(store: NudgeStore) -> None:
    first = _record(nudge_id="nudge_first")
    second = _record(nudge_id="nudge_second")
    store.append(first)
    store.append(second)
    assert [r.nudge_id for r in store.all()] == ["nudge_first", "nudge_second"]


# --------------------------------------------------------------------------- #
# Restart survival (SQLite-only by nature): state written before a process
# exit must be fully recovered by a fresh store instance on the same file.
# --------------------------------------------------------------------------- #


def test_sqlite_state_survives_restart(tmp_path: Path) -> None:
    db_path = tmp_path / "store.db"
    db = SqliteDatabase(db_path)
    first = SqliteNudgeStore(db)
    mine = _record(nudge_id="nudge_a")
    other_user = _record(nudge_id="nudge_b", user_id="user_999")
    first.append(mine)
    first.append(other_user)
    db.close()

    reopened = SqliteNudgeStore(SqliteDatabase(db_path))
    assert reopened.get("nudge_a") == mine
    assert reopened.list_for_user("user_123") == [mine]
    assert reopened.all() == [mine, other_user]
