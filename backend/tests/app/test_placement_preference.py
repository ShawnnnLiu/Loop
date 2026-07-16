"""Tests for the ``PlacementPreferenceStore`` implementations (P-I).

The behavioral suite is parametrized over the in-memory and SQLite
implementations (Phase 9a kernel): both must satisfy the protocol
identically. Restart survival at the bottom is SQLite-only by nature — a
revealed preference the user demonstrated last month must outlive the
process to bias next month's replan.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from agentic_calendar.app.placement_preference import (
    InMemoryPlacementPreferenceStore,
    PlacementPreferenceAlreadyExistsError,
    PlacementPreferenceStore,
    SqlitePlacementPreferenceStore,
)
from agentic_calendar.common.sqlite import SqliteDatabase
from agentic_calendar.contracts.common_types import TaskCategory
from agentic_calendar.contracts.placement_preference import (
    PlacementPreferenceObservation,
    PlacementPreferenceSource,
)
from agentic_calendar.contracts.pooled_duration_model import TimeOfDayBand

_T0 = datetime(2026, 7, 16, 18, 0, 0, tzinfo=UTC)


@pytest.fixture(params=["in_memory", "sqlite"])
def store(request: pytest.FixtureRequest, tmp_path: Path) -> PlacementPreferenceStore:
    if request.param == "sqlite":
        return SqlitePlacementPreferenceStore(SqliteDatabase(tmp_path / "store.db"))
    return InMemoryPlacementPreferenceStore()


def _observation(
    observation_id: str = "prefobs_001",
    *,
    user_id: str = "user_123",
    task_id: str = "dp_001",
    category: TaskCategory = TaskCategory.PRACTICE,
    band: TimeOfDayBand = TimeOfDayBand.EVENING,
    source: PlacementPreferenceSource = PlacementPreferenceSource.DRAG_ADJUST,
    offset_minutes: int = 0,
) -> PlacementPreferenceObservation:
    return PlacementPreferenceObservation(
        observation_id=observation_id,
        user_id=user_id,
        task_id=task_id,
        category=category,
        time_of_day_band=band,
        observed_at=_T0 + timedelta(minutes=offset_minutes),
        source=source,
    )


def test_satisfies_protocol(store: PlacementPreferenceStore) -> None:
    """Both implementations structurally satisfy the runtime-checkable protocol."""
    assert isinstance(store, PlacementPreferenceStore)


def test_append_and_list_round_trip(store: PlacementPreferenceStore) -> None:
    """A journaled observation is recovered exactly (contract-validated round trip)."""
    observation = _observation()
    store.append(observation)
    assert store.list_for_user("user_123") == [observation]


def test_list_for_user_scopes_and_preserves_insertion_order(
    store: PlacementPreferenceStore,
) -> None:
    """Per-user listing returns only that user's rows, in append order — the
    ordering the read-time aggregation window relies on."""
    first = _observation("prefobs_001")
    other = _observation("prefobs_002", user_id="user_456", offset_minutes=5)
    second = _observation(
        "prefobs_003",
        task_id="dp_002",
        source=PlacementPreferenceSource.RECONCILE_ADOPT,
        offset_minutes=10,
    )
    store.append(first)
    store.append(other)
    store.append(second)
    assert store.list_for_user("user_123") == [first, second]
    assert store.list_for_user("user_456") == [other]
    assert store.list_for_user("user_789") == []


def test_duplicate_observation_id_raises(store: PlacementPreferenceStore) -> None:
    """Observations are immutable facts: rewriting one would silently rewrite
    the revealed-preference evidence the scheduler serves from."""
    store.append(_observation("prefobs_dup"))
    with pytest.raises(PlacementPreferenceAlreadyExistsError):
        store.append(_observation("prefobs_dup", task_id="dp_999"))
    assert len(store.list_for_user("user_123")) == 1


def test_delete_for_user_removes_only_that_user(
    store: PlacementPreferenceStore,
) -> None:
    """The data-control surface: delete returns the removed count and leaves
    other users' rows untouched (placement-preference spec)."""
    store.append(_observation("prefobs_001"))
    store.append(_observation("prefobs_002", task_id="dp_002", offset_minutes=5))
    kept = _observation("prefobs_003", user_id="user_456", offset_minutes=10)
    store.append(kept)

    assert store.delete_for_user("user_123") == 2
    assert store.list_for_user("user_123") == []
    assert store.list_for_user("user_456") == [kept]
    assert store.delete_for_user("user_123") == 0


def test_sqlite_observations_survive_restart(tmp_path: Path) -> None:
    """Rows written before close are recovered exactly by a fresh store on
    the same path — a revealed preference must outlive the process."""
    db_path = tmp_path / "store.db"
    db = SqliteDatabase(db_path)
    first_store = SqlitePlacementPreferenceStore(db)
    first = _observation("prefobs_001")
    second = _observation(
        "prefobs_002",
        source=PlacementPreferenceSource.RECONCILE_ADOPT,
        offset_minutes=5,
    )
    first_store.append(first)
    first_store.append(second)
    db.close()

    reopened = SqlitePlacementPreferenceStore(SqliteDatabase(db_path))
    assert reopened.list_for_user("user_123") == [first, second]
    with pytest.raises(PlacementPreferenceAlreadyExistsError):
        reopened.append(_observation("prefobs_001"))
