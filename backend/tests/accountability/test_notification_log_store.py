"""Unit tests for ``InMemoryNotificationLogStore`` (Phase 3)."""

from __future__ import annotations

import threading
from datetime import UTC, datetime

import pytest

from agentic_calendar.accountability.notification_log_store import (
    InMemoryNotificationLogStore,
    NotificationLogAlreadyExistsError,
    NotificationLogStore,
)
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


# ---------------------------------------------------------------------------
# 1. Protocol conformance
# ---------------------------------------------------------------------------


def test_satisfies_protocol() -> None:
    assert isinstance(InMemoryNotificationLogStore(), NotificationLogStore)


# ---------------------------------------------------------------------------
# 2. Basic append / list round-trip
# ---------------------------------------------------------------------------


def test_append_then_list_for_report() -> None:
    store = InMemoryNotificationLogStore()
    log = _log()
    store.append(log)
    assert store.list_for_report("rpt_1") == [log]


def test_append_then_list_for_user() -> None:
    store = InMemoryNotificationLogStore()
    log = _log()
    store.append(log)
    assert store.list_for_user("user_1") == [log]


# ---------------------------------------------------------------------------
# 3. Duplicate id raises NotificationLogAlreadyExistsError
# ---------------------------------------------------------------------------


def test_duplicate_id_raises() -> None:
    store = InMemoryNotificationLogStore()
    log = _log()
    store.append(log)
    with pytest.raises(NotificationLogAlreadyExistsError):
        store.append(log)


# ---------------------------------------------------------------------------
# 4. Insertion order preserved
# ---------------------------------------------------------------------------


def test_insertion_order_preserved_list_for_report() -> None:
    store = InMemoryNotificationLogStore()
    log_a = _log(notification_log_id="notif_a")
    log_b = _log(notification_log_id="notif_b")
    log_c = _log(notification_log_id="notif_c")
    for entry in (log_a, log_b, log_c):
        store.append(entry)
    assert store.list_for_report("rpt_1") == [log_a, log_b, log_c]


# ---------------------------------------------------------------------------
# 5. Filtering by report_id and user_id
# ---------------------------------------------------------------------------


def test_list_for_report_filters_other_report_ids() -> None:
    store = InMemoryNotificationLogStore()
    log_rpt1 = _log(notification_log_id="notif_1", report_id="rpt_1")
    log_rpt2 = _log(notification_log_id="notif_2", report_id="rpt_2")
    store.append(log_rpt1)
    store.append(log_rpt2)
    assert store.list_for_report("rpt_1") == [log_rpt1]
    assert store.list_for_report("rpt_2") == [log_rpt2]


def test_list_for_user_filters_other_user_ids() -> None:
    store = InMemoryNotificationLogStore()
    log_u1 = _log(notification_log_id="notif_1", user_id="user_1")
    log_u2 = _log(notification_log_id="notif_2", user_id="user_2")
    store.append(log_u1)
    store.append(log_u2)
    assert store.list_for_user("user_1") == [log_u1]
    assert store.list_for_user("user_2") == [log_u2]


# ---------------------------------------------------------------------------
# 6. Empty store returns empty list
# ---------------------------------------------------------------------------


def test_list_for_report_empty_store() -> None:
    store = InMemoryNotificationLogStore()
    assert store.list_for_report("rpt_1") == []


def test_list_for_user_empty_store() -> None:
    store = InMemoryNotificationLogStore()
    assert store.list_for_user("user_1") == []


# ---------------------------------------------------------------------------
# 7. Thread-safety: 8 threads x 50 unique logs = 400 total
# ---------------------------------------------------------------------------


def test_thread_safety() -> None:
    store = InMemoryNotificationLogStore()
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
# 8. Append-only / no-mutation: list_for_report returns exact same object
# ---------------------------------------------------------------------------


def test_store_does_not_copy_or_alter_log() -> None:
    store = InMemoryNotificationLogStore()
    log = _log()
    store.append(log)
    retrieved = store.list_for_report("rpt_1")
    assert len(retrieved) == 1
    # Must be the identical object — the store must not wrap or copy it.
    assert retrieved[0] is log
