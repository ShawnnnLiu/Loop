"""Tests for the ``ThresholdChangeLogStore`` implementations (Phase 9d).

The behavioral suite is parametrized over the in-memory and SQLite
implementations (Phase 9a kernel): both must satisfy the protocol
identically. Restart survival at the bottom is SQLite-only by nature —
axiom 07's journal is worthless if it does not outlive the process.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from agentic_calendar.app.threshold_log import (
    InMemoryThresholdChangeLogStore,
    SqliteThresholdChangeLogStore,
    ThresholdChangeAlreadyExistsError,
    ThresholdChangeLogStore,
)
from agentic_calendar.common.sqlite import SqliteDatabase
from agentic_calendar.contracts.threshold_change_log import ThresholdChange

_T0 = datetime(2026, 6, 11, 12, 0, 0, tzinfo=UTC)


@pytest.fixture(params=["in_memory", "sqlite"])
def store(request: pytest.FixtureRequest, tmp_path: Path) -> ThresholdChangeLogStore:
    if request.param == "sqlite":
        return SqliteThresholdChangeLogStore(SqliteDatabase(tmp_path / "store.db"))
    return InMemoryThresholdChangeLogStore()


def _change(
    change_id: str = "thrchg_001",
    *,
    config_section: str = "drift_thresholds",
    threshold_field: str = "duration_underestimate_ratio",
    prior_value: int | float = 1.3,
    new_value: int | float = 1.4,
    offset_minutes: int = 0,
) -> ThresholdChange:
    return ThresholdChange(
        change_id=change_id,
        config_section=config_section,
        threshold_field=threshold_field,
        prior_value=prior_value,
        new_value=new_value,
        effective_at=_T0 + timedelta(minutes=offset_minutes),
        justification="Loosened after repeated false positives in dogfooding.",
        dataset_reference="telemetry through 2026-06-10",
    )


def test_satisfies_protocol(store: ThresholdChangeLogStore) -> None:
    """Both implementations structurally satisfy the runtime-checkable protocol."""
    assert isinstance(store, ThresholdChangeLogStore)


def test_append_and_list_all_round_trip(store: ThresholdChangeLogStore) -> None:
    """A journaled change is recovered exactly (contract-validated round trip)."""
    change = _change()
    store.append(change)
    assert store.list_all() == [change]


def test_list_all_preserves_insertion_order(store: ThresholdChangeLogStore) -> None:
    """Insertion order is the replay contract: the last entry per field wins,
    so reordering would silently change effective values."""
    first = _change("thrchg_001", new_value=1.4)
    second = _change("thrchg_002", prior_value=1.4, new_value=1.5, offset_minutes=5)
    third = _change(
        "thrchg_003",
        config_section="pooled_serving",
        threshold_field="serving_floor",
        prior_value=5.0,
        new_value=6.0,
        offset_minutes=10,
    )
    store.append(first)
    store.append(second)
    store.append(third)
    assert store.list_all() == [first, second, third]


def test_list_for_field_filters_and_preserves_order(
    store: ThresholdChangeLogStore,
) -> None:
    """Per-field listing scopes by (section, field) without reordering."""
    ratio_1 = _change("thrchg_001", new_value=1.4)
    floor = _change(
        "thrchg_002",
        config_section="pooled_serving",
        threshold_field="serving_floor",
        prior_value=5.0,
        new_value=6.0,
        offset_minutes=5,
    )
    ratio_2 = _change("thrchg_003", prior_value=1.4, new_value=1.5, offset_minutes=10)
    store.append(ratio_1)
    store.append(floor)
    store.append(ratio_2)
    assert store.list_for_field(
        "drift_thresholds", "duration_underestimate_ratio"
    ) == [ratio_1, ratio_2]
    assert store.list_for_field("pooled_serving", "serving_floor") == [floor]
    assert store.list_for_field("drift_thresholds", "duration_min_sample") == []


def test_duplicate_change_id_raises(store: ThresholdChangeLogStore) -> None:
    """Entries are immutable audit facts: rewriting one would rewrite history
    (axiom 07 'no silent threshold changes')."""
    store.append(_change("thrchg_dup"))
    with pytest.raises(ThresholdChangeAlreadyExistsError):
        store.append(_change("thrchg_dup", prior_value=1.4, new_value=1.5))
    assert len(store.list_all()) == 1


def test_sqlite_journal_survives_restart(tmp_path: Path) -> None:
    """Entries written before close are recovered exactly by a fresh store on
    the same path — the property deterministic replay depends on."""
    db_path = tmp_path / "store.db"
    db = SqliteDatabase(db_path)
    first_store = SqliteThresholdChangeLogStore(db)
    first = _change("thrchg_001")
    second = _change("thrchg_002", prior_value=1.4, new_value=1.5, offset_minutes=5)
    first_store.append(first)
    first_store.append(second)
    db.close()

    reopened = SqliteThresholdChangeLogStore(SqliteDatabase(db_path))
    assert reopened.list_all() == [first, second]
    assert reopened.list_for_field(
        "drift_thresholds", "duration_underestimate_ratio"
    ) == [first, second]
    with pytest.raises(ThresholdChangeAlreadyExistsError):
        reopened.append(_change("thrchg_001"))
