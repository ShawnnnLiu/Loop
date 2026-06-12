"""Tests for the ``NotificationLogStore`` implementations.

The behavioral suite is parametrized over the in-memory and SQLite
implementations (Phase 9a): both must satisfy the protocol identically.
The restart-survival test at the bottom is SQLite-only by nature.
"""

from __future__ import annotations

import threading
from datetime import UTC, datetime
from pathlib import Path

import pytest

from agentic_calendar.accountability.notification_log_store import (
    InMemoryNotificationLogStore,
    NotificationLogAlreadyExistsError,
    NotificationLogStore,
)
from agentic_calendar.accountability.sqlite_notification_log_store import (
    SqliteNotificationLogStore,
)
from agentic_calendar.common.sqlite import SqliteDatabase
from agentic_calendar.contracts.motivation_profile import NudgeChannel, SponsorVisibility
from agentic_calendar.contracts.notification_log import NotificationLog, NotificationStatus

_CREATED_AT = datetime(2026, 5, 10, tzinfo=UTC)


def _log(**overrides: object) -> NotificationLog:
    """Return a valid SENT ``NotificationLog`` with sensible defaults."""
    defaults: dict[str, object] = {
        "notification_log_id": "notif_1",
        "report_id": "rpt_1",
        "sponsor_id": "sponsor_1",
        "user_id": "user_1",
        "visibility_level": SponsorVisibility.SUMMARY_ONLY,
        "channel": NudgeChannel.EMAIL,
        "status": NotificationStatus.SENT,
        "reason_code": None,
        "created_at": _CREATED_AT,
    }
    defaults.update(overrides)
    return NotificationLog(**defaults)  # type: ignore[arg-type]


@pytest.fixture(params=["in_memory", "sqlite"])
def store(request: pytest.FixtureRequest, tmp_path: Path) -> NotificationLogStore:
    if request.param == "sqlite":
        return SqliteNotificationLogStore(SqliteDatabase(tmp_path / "store.db"))
    return InMemoryNotificationLogStore()


# ---------------------------------------------------------------------------
# 1. Protocol conformance
# ---------------------------------------------------------------------------


def test_satisfies_protocol(store: NotificationLogStore) -> None:
    assert isinstance(store, NotificationLogStore)


# ---------------------------------------------------------------------------
# 2. Basic append / list round-trip
# ---------------------------------------------------------------------------


def test_append_then_list_for_report(store: NotificationLogStore) -> None:
    log = _log()
    store.append(log)
    assert store.list_for_report("rpt_1") == [log]


def test_append_then_list_for_user(store: NotificationLogStore) -> None:
    log = _log()
    store.append(log)
    assert store.list_for_user("user_1") == [log]


# ---------------------------------------------------------------------------
# 3. Duplicate id raises NotificationLogAlreadyExistsError
# ---------------------------------------------------------------------------


def test_duplicate_id_raises(store: NotificationLogStore) -> None:
    log = _log()
    store.append(log)
    with pytest.raises(NotificationLogAlreadyExistsError):
        store.append(log)


# ---------------------------------------------------------------------------
# 4. Insertion order preserved
# ---------------------------------------------------------------------------


def test_insertion_order_preserved_list_for_report(store: NotificationLogStore) -> None:
    log_a = _log(notification_log_id="notif_a")
    log_b = _log(notification_log_id="notif_b")
    log_c = _log(notification_log_id="notif_c")
    for entry in (log_a, log_b, log_c):
        store.append(entry)
    assert store.list_for_report("rpt_1") == [log_a, log_b, log_c]


# ---------------------------------------------------------------------------
# 5. Filtering by report_id and user_id
# ---------------------------------------------------------------------------


def test_list_for_report_filters_other_report_ids(store: NotificationLogStore) -> None:
    log_rpt1 = _log(notification_log_id="notif_1", report_id="rpt_1")
    log_rpt2 = _log(notification_log_id="notif_2", report_id="rpt_2")
    store.append(log_rpt1)
    store.append(log_rpt2)
    assert store.list_for_report("rpt_1") == [log_rpt1]
    assert store.list_for_report("rpt_2") == [log_rpt2]


def test_list_for_user_filters_other_user_ids(store: NotificationLogStore) -> None:
    log_u1 = _log(notification_log_id="notif_1", user_id="user_1")
    log_u2 = _log(notification_log_id="notif_2", user_id="user_2")
    store.append(log_u1)
    store.append(log_u2)
    assert store.list_for_user("user_1") == [log_u1]
    assert store.list_for_user("user_2") == [log_u2]


# ---------------------------------------------------------------------------
# 6. Empty store returns empty list
# ---------------------------------------------------------------------------


def test_list_for_report_empty_store(store: NotificationLogStore) -> None:
    assert store.list_for_report("rpt_1") == []


def test_list_for_user_empty_store(store: NotificationLogStore) -> None:
    assert store.list_for_user("user_1") == []


# ---------------------------------------------------------------------------
# 7. Thread-safety: 8 threads x 50 unique logs = 400 total
# ---------------------------------------------------------------------------


def test_thread_safety(store: NotificationLogStore) -> None:
    threads_count = 8
    logs_per_thread = 50
    errors: list[Exception] = []

    def worker(t: int) -> None:
        try:
            for i in range(logs_per_thread):
                store.append(_log(notification_log_id=f"notif_{t}_{i}"))
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(t,)) for t in range(threads_count)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()

    assert errors == [], f"Thread(s) raised: {errors}"
    assert len(store.list_for_user("user_1")) == threads_count * logs_per_thread


# ---------------------------------------------------------------------------
# 8. Append-only / no-mutation: list_for_report returns an equal record
# ---------------------------------------------------------------------------


def test_store_does_not_alter_log(store: NotificationLogStore) -> None:
    log = _log()
    store.append(log)
    retrieved = store.list_for_report("rpt_1")
    assert len(retrieved) == 1
    # Must round-trip unchanged — the store must not wrap or alter it.
    assert retrieved[0] == log


# --------------------------------------------------------------------------- #
# Restart survival (SQLite-only by nature): state written before a process
# exit must be fully recovered by a fresh store instance on the same file.
# --------------------------------------------------------------------------- #


def test_sqlite_state_survives_restart(tmp_path: Path) -> None:
    db_path = tmp_path / "store.db"
    db = SqliteDatabase(db_path)
    first = SqliteNotificationLogStore(db)
    log_a = _log(notification_log_id="notif_a")
    log_b = _log(notification_log_id="notif_b", report_id="rpt_2", user_id="user_2")
    first.append(log_a)
    first.append(log_b)
    db.close()

    reopened = SqliteNotificationLogStore(SqliteDatabase(db_path))
    assert reopened.list_for_report("rpt_1") == [log_a]
    assert reopened.list_for_report("rpt_2") == [log_b]
    assert reopened.list_for_user("user_1") == [log_a]
    assert reopened.list_for_user("user_2") == [log_b]
