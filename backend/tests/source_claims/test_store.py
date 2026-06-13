"""Tests for the ``SourceClaimStore`` implementations.

The behavioral suite is parametrized over the in-memory and SQLite
implementations (Phase 9a): both must satisfy the protocol identically.
The restart-survival test at the bottom is SQLite-only by nature.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from agentic_calendar.common.sqlite import SqliteDatabase
from agentic_calendar.contracts.source_claim import SourceClaim
from agentic_calendar.source_claims.ingestion import (
    InMemorySourceClaimStore,
    SourceClaimAlreadyExistsError,
    SourceClaimStore,
)
from agentic_calendar.source_claims.sqlite_store import SqliteSourceClaimStore
from tests._fixture_loader import iter_valid


@pytest.fixture(params=["in_memory", "sqlite"])
def store(request: pytest.FixtureRequest, tmp_path: Path) -> SourceClaimStore:
    if request.param == "sqlite":
        return SqliteSourceClaimStore(SqliteDatabase(tmp_path / "store.db"))
    return InMemorySourceClaimStore()


def _make_claim(claim_id: str) -> SourceClaim:
    base = SourceClaim.model_validate(next(iter_valid("source_claim")).payload)
    return base.model_copy(update={"claim_id": claim_id})


def test_satisfies_protocol(store: SourceClaimStore) -> None:
    assert isinstance(store, SourceClaimStore)


def test_append_and_get_round_trip(store: SourceClaimStore) -> None:
    claim = _make_claim("c_001")
    store.append(claim)
    assert store.get("c_001") == claim


def test_append_rejects_duplicate_id(store: SourceClaimStore) -> None:
    claim = _make_claim("c_001")
    store.append(claim)
    with pytest.raises(SourceClaimAlreadyExistsError):
        store.append(claim)
    assert len(store.all()) == 1


def test_exists(store: SourceClaimStore) -> None:
    store.append(_make_claim("c_001"))
    assert store.exists("c_001")
    assert not store.exists("c_missing")


def test_get_missing_returns_none(store: SourceClaimStore) -> None:
    assert store.get("c_missing") is None


def test_all_preserves_insertion_order(store: SourceClaimStore) -> None:
    claims = [_make_claim(f"c_{i:03d}") for i in range(5)]
    for claim in claims:
        store.append(claim)
    assert store.all() == claims


# --------------------------------------------------------------------------- #
# Restart survival (SQLite-only by nature): state written before a process
# exit must be fully recovered by a fresh store instance on the same file.
# --------------------------------------------------------------------------- #


def test_sqlite_state_survives_restart(tmp_path: Path) -> None:
    db_path = tmp_path / "store.db"
    db = SqliteDatabase(db_path)
    first = SqliteSourceClaimStore(db)
    a = _make_claim("c_a")
    b = _make_claim("c_b")
    first.append(a)
    first.append(b)
    db.close()

    reopened = SqliteSourceClaimStore(SqliteDatabase(db_path))
    assert reopened.all() == [a, b]
    assert reopened.exists("c_a")
    assert reopened.get("c_b") == b
