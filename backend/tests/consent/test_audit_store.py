"""Tests for the ``DataAccessAuditStore`` implementations.

The behavioral suite is parametrized over the in-memory and SQLite
implementations (Phase 9a): both must satisfy the protocol identically.
The restart-survival test at the bottom is SQLite-only by nature.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from agentic_calendar.common.sqlite import SqliteDatabase
from agentic_calendar.consent.audit_store import (
    AuditEntryAlreadyExistsError,
    DataAccessAuditStore,
    InMemoryDataAccessAuditStore,
)
from agentic_calendar.consent.sqlite_audit_store import SqliteDataAccessAuditStore
from agentic_calendar.contracts.data_access_audit import (
    DataAccessAuditEntry,
    DataAccessor,
    DataAccessOutcome,
    DataAccessPurpose,
)

from ._builders import T0


@pytest.fixture(params=["in_memory", "sqlite"])
def store(request: pytest.FixtureRequest, tmp_path: Path) -> DataAccessAuditStore:
    if request.param == "sqlite":
        return SqliteDataAccessAuditStore(SqliteDatabase(tmp_path / "store.db"))
    return InMemoryDataAccessAuditStore()


def _entry(entry_id: str, user_id: str = "user_123") -> DataAccessAuditEntry:
    return DataAccessAuditEntry(
        audit_entry_id=entry_id,
        user_id=user_id,
        purpose=DataAccessPurpose.POOLED_TRAINING,
        accessor=DataAccessor.TRAINING_PIPELINE,
        outcome=DataAccessOutcome.ALLOWED,
        reason_code=None,
        created_at=T0,
    )


def test_satisfies_protocol(store: DataAccessAuditStore) -> None:
    assert isinstance(store, DataAccessAuditStore)


def test_append_and_list_in_insertion_order(store: DataAccessAuditStore) -> None:
    store.append(_entry("audit_001"))
    store.append(_entry("audit_002", user_id="user_456"))
    store.append(_entry("audit_003"))
    assert [e.audit_entry_id for e in store.list_for_user("user_123")] == [
        "audit_001",
        "audit_003",
    ]
    assert [e.audit_entry_id for e in store.all()] == ["audit_001", "audit_002", "audit_003"]


def test_append_rejects_duplicate_id(store: DataAccessAuditStore) -> None:
    store.append(_entry("audit_001"))
    with pytest.raises(AuditEntryAlreadyExistsError):
        store.append(_entry("audit_001"))


def test_no_delete_surface_exists(store: DataAccessAuditStore) -> None:
    """Audit entries survive a user-data deletion (data-access-audit spec)."""
    assert not hasattr(store, "delete_for_user")


# --------------------------------------------------------------------------- #
# Restart survival (SQLite-only by nature): state written before a process
# exit must be fully recovered by a fresh store instance on the same file.
# --------------------------------------------------------------------------- #


def test_sqlite_state_survives_restart(tmp_path: Path) -> None:
    db_path = tmp_path / "store.db"
    db = SqliteDatabase(db_path)
    first = SqliteDataAccessAuditStore(db)
    e1 = _entry("audit_001")
    e2 = _entry("audit_002", user_id="user_456")
    e3 = _entry("audit_003")
    first.append(e1)
    first.append(e2)
    first.append(e3)
    db.close()

    reopened = SqliteDataAccessAuditStore(SqliteDatabase(db_path))
    assert reopened.all() == [e1, e2, e3]
    assert reopened.list_for_user("user_123") == [e1, e3]
    assert reopened.list_for_user("user_456") == [e2]
