"""Tests for ``InMemoryDataAccessAuditStore`` append-only behavior."""

from __future__ import annotations

import pytest

from agentic_calendar.consent.audit_store import (
    AuditEntryAlreadyExistsError,
    DataAccessAuditStore,
    InMemoryDataAccessAuditStore,
)
from agentic_calendar.contracts.data_access_audit import (
    DataAccessAuditEntry,
    DataAccessor,
    DataAccessOutcome,
    DataAccessPurpose,
)

from ._builders import T0


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


def test_satisfies_protocol() -> None:
    assert isinstance(InMemoryDataAccessAuditStore(), DataAccessAuditStore)


def test_append_and_list_in_insertion_order() -> None:
    store = InMemoryDataAccessAuditStore()
    store.append(_entry("audit_001"))
    store.append(_entry("audit_002", user_id="user_456"))
    store.append(_entry("audit_003"))
    assert [e.audit_entry_id for e in store.list_for_user("user_123")] == [
        "audit_001",
        "audit_003",
    ]
    assert [e.audit_entry_id for e in store.all()] == ["audit_001", "audit_002", "audit_003"]


def test_append_rejects_duplicate_id() -> None:
    store = InMemoryDataAccessAuditStore()
    store.append(_entry("audit_001"))
    with pytest.raises(AuditEntryAlreadyExistsError):
        store.append(_entry("audit_001"))


def test_no_delete_surface_exists() -> None:
    """Audit entries survive a user-data deletion (data-access-audit spec)."""
    store = InMemoryDataAccessAuditStore()
    assert not hasattr(store, "delete_for_user")
