"""Tests for ``TelemetryEvent`` and ``DataQuality``."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from agentic_calendar.contracts.telemetry import DataQuality, TelemetryEvent
from tests._fixture_loader import iter_invalid, iter_valid

CONTRACT = "telemetry"


@pytest.mark.parametrize(
    "fixture",
    list(iter_valid(CONTRACT)),
    ids=lambda f: f.name,
)
def test_valid_fixture_parses(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    event = TelemetryEvent.model_validate(payload)
    assert event.telemetry_event_id == payload["telemetry_event_id"]


@pytest.mark.parametrize(
    "fixture",
    list(iter_invalid(CONTRACT)),
    ids=lambda f: f.name,
)
def test_invalid_fixture_rejected(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    expected = fixture.expected  # type: ignore[attr-defined]
    with pytest.raises(ValidationError) as exc_info:
        TelemetryEvent.model_validate(payload)
    msg = str(exc_info.value)
    for substr in expected["error_substrings"]:
        assert substr in msg, (
            f"expected substring {substr!r} not in error message:\n{msg}"
        )


def test_defaults_applied() -> None:
    """duration_estimated and captured_offline default to False."""
    minimal = {
        "telemetry_event_id": "tel_default_001",
        "task_id": "dp_default",
        "scheduled_duration_min": 60,
        "completed": False,
        "user_reschedule_count": 0,
        "data_quality": "complete",
    }
    event = TelemetryEvent.model_validate(minimal)
    assert event.duration_estimated is False
    assert event.captured_offline is False
    assert event.actual_duration_min is None
    assert event.completion_timestamp is None


def test_incomplete_does_not_require_actuals() -> None:
    """completed=False permits null actual_duration_min and completion_timestamp."""
    payload = {
        "telemetry_event_id": "tel_incomplete_unit",
        "task_id": "dp_unit",
        "scheduled_duration_min": 45,
        "completed": False,
        "user_reschedule_count": 1,
        "data_quality": DataQuality.COMPLETE,
    }
    event = TelemetryEvent.model_validate(payload)
    assert event.completed is False
    assert event.actual_duration_min is None
