"""Tests for ``CheckinEvent``."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from agentic_calendar.contracts.checkin_event import CheckinEvent, RecoveryAction
from tests._fixture_loader import iter_invalid, iter_valid

CONTRACT = "checkin_event"


@pytest.mark.parametrize(
    "fixture",
    list(iter_valid(CONTRACT)),
    ids=lambda f: f.name,
)
def test_valid_fixture_parses(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    event = CheckinEvent.model_validate(payload)
    assert event.checkin_id == payload["checkin_id"]


@pytest.mark.parametrize(
    "fixture",
    list(iter_invalid(CONTRACT)),
    ids=lambda f: f.name,
)
def test_invalid_fixture_rejected(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    expected = fixture.expected  # type: ignore[attr-defined]
    with pytest.raises(ValidationError) as exc_info:
        CheckinEvent.model_validate(payload)
    msg = str(exc_info.value)
    for substr in expected["error_substrings"]:
        assert substr in msg, f"expected substring {substr!r} not in error message:\n{msg}"


def test_recovery_action_excludes_ask_each_time() -> None:
    """``ask_each_time`` is a preference, never a submitted answer (spec)."""
    assert "ask_each_time" not in {a.value for a in RecoveryAction}


def test_overshoot_is_valid() -> None:
    """Completing more than scheduled is legal; behind-math clamps downstream."""
    event = CheckinEvent.model_validate(
        {
            "checkin_id": "checkin_o",
            "user_id": "user_o",
            "plan_id": "plan_o",
            "week_start": "2026-05-04",
            "week_end": "2026-05-10",
            "completed_task_count": 7,
            "scheduled_task_count": 6,
            "completed_minutes": 420,
            "scheduled_minutes": 360,
            "created_at": "2026-05-10T19:00:00-07:00",
        }
    )
    assert event.completed_minutes > event.scheduled_minutes
