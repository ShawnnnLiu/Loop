"""Tests for the ``GoogleCredentialStore`` implementations.

Parametrized over the in-memory and SQLite twins (Phase 9a pattern): both must
satisfy the protocol identically, including the 1:1 sub<->user_id invariant.
The restart-survival test at the bottom is SQLite-only by nature.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from agentic_calendar.common.sqlite import SqliteDatabase
from agentic_calendar.identity.sqlite_store import SqliteGoogleCredentialStore
from agentic_calendar.identity.store import (
    GoogleCredentialRecord,
    GoogleCredentialStore,
    GoogleSubConflictError,
    InMemoryGoogleCredentialStore,
)

T0 = datetime(2026, 5, 4, 12, 0, tzinfo=UTC)
AnyStore = InMemoryGoogleCredentialStore | SqliteGoogleCredentialStore


def _record(
    *,
    user_id: str = "user_1",
    google_sub: str = "sub_1",
    email: str = "a@example.com",
    encrypted_token: str = "ciphertext",
    dedicated_calendar_id: str | None = None,
) -> GoogleCredentialRecord:
    return GoogleCredentialRecord(
        user_id=user_id,
        google_sub=google_sub,
        email=email,
        encrypted_token=encrypted_token,
        dedicated_calendar_id=dedicated_calendar_id,
        created_at=T0,
        updated_at=T0,
    )


@pytest.fixture(params=["in_memory", "sqlite"])
def store(request: pytest.FixtureRequest, tmp_path: Path) -> AnyStore:
    if request.param == "sqlite":
        return SqliteGoogleCredentialStore(SqliteDatabase(tmp_path / "identity.db"))
    return InMemoryGoogleCredentialStore()


def test_satisfies_protocol(store: AnyStore) -> None:
    assert isinstance(store, GoogleCredentialStore)


def test_save_then_get(store: AnyStore) -> None:
    store.save(_record())
    got = store.get_by_user("user_1")
    assert got is not None
    assert got.google_sub == "sub_1"
    assert got.email == "a@example.com"


def test_get_missing_returns_none(store: AnyStore) -> None:
    assert store.get_by_user("nobody") is None


def test_get_user_id_for_sub(store: AnyStore) -> None:
    store.save(_record())
    assert store.get_user_id_for_sub("sub_1") == "user_1"
    assert store.get_user_id_for_sub("unknown") is None


def test_save_upserts_same_user(store: AnyStore) -> None:
    store.save(_record(encrypted_token="ct1"))
    store.save(_record(encrypted_token="ct2", dedicated_calendar_id="cal_x"))
    got = store.get_by_user("user_1")
    assert got is not None
    assert got.encrypted_token == "ct2"
    assert got.dedicated_calendar_id == "cal_x"


def test_sub_conflict_is_rejected(store: AnyStore) -> None:
    store.save(_record(user_id="user_1", google_sub="shared"))
    with pytest.raises(GoogleSubConflictError):
        store.save(_record(user_id="user_2", google_sub="shared"))
    # The original linkage is untouched.
    assert store.get_user_id_for_sub("shared") == "user_1"
    assert store.get_by_user("user_2") is None


def test_delete_for_user(store: AnyStore) -> None:
    store.save(_record())
    assert store.delete_for_user("user_1") == 1
    assert store.get_by_user("user_1") is None
    assert store.delete_for_user("user_1") == 0


def test_restart_survival(tmp_path: Path) -> None:
    path = tmp_path / "identity.db"
    SqliteGoogleCredentialStore(SqliteDatabase(path)).save(
        _record(dedicated_calendar_id="cal_persist")
    )
    reopened = SqliteGoogleCredentialStore(SqliteDatabase(path))
    got = reopened.get_by_user("user_1")
    assert got is not None
    assert got.dedicated_calendar_id == "cal_persist"
