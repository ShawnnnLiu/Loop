"""Tests for ``NotificationLog``."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from agentic_calendar.contracts.notification_log import NotificationLog
from tests._fixture_loader import iter_invalid, iter_valid

CONTRACT = "notification_log"


@pytest.mark.parametrize(
    "fixture",
    list(iter_valid(CONTRACT)),
    ids=lambda f: f.name,
)
def test_valid_fixture_parses(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    nl = NotificationLog.model_validate(payload)
    assert nl.notification_log_id == payload["notification_log_id"]


@pytest.mark.parametrize(
    "fixture",
    list(iter_invalid(CONTRACT)),
    ids=lambda f: f.name,
)
def test_invalid_fixture_rejected(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    expected = fixture.expected  # type: ignore[attr-defined]
    with pytest.raises(ValidationError) as exc_info:
        NotificationLog.model_validate(payload)
    msg = str(exc_info.value)
    for substr in expected["error_substrings"]:
        assert substr in msg, (
            f"expected substring {substr!r} not in error message:\n{msg}"
        )


def test_defaults_applied() -> None:
    """engineering_review and dry_run default to False on a minimal valid sent entry."""
    minimal = {
        "notification_log_id": "nlog_default_001",
        "report_id": "report_default_001",
        "sponsor_id": "sponsor_default",
        "user_id": "user_default",
        "visibility_level": "summary_only",
        "channel": "email",
        "status": "sent",
        "created_at": "2026-05-10T19:12:00-07:00",
    }
    nl = NotificationLog.model_validate(minimal)
    assert nl.engineering_review is False
    assert nl.dry_run is False
