"""Tests for ``NudgeRecord``."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from agentic_calendar.contracts.nudge import (
    ALLOWED_NUDGE_REASON_CODES,
    NudgeRecord,
)
from agentic_calendar.contracts.reason_codes import ReasonCode
from tests._fixture_loader import iter_invalid, iter_valid

CONTRACT = "nudge"


@pytest.mark.parametrize(
    "fixture",
    list(iter_valid(CONTRACT)),
    ids=lambda f: f.name,
)
def test_valid_fixture_parses(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    nudge = NudgeRecord.model_validate(payload)
    assert nudge.nudge_id == payload["nudge_id"]


@pytest.mark.parametrize(
    "fixture",
    list(iter_invalid(CONTRACT)),
    ids=lambda f: f.name,
)
def test_invalid_fixture_rejected(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    expected = fixture.expected  # type: ignore[attr-defined]
    with pytest.raises(ValidationError) as exc_info:
        NudgeRecord.model_validate(payload)
    msg = str(exc_info.value)
    for substr in expected["error_substrings"]:
        assert substr in msg, f"expected substring {substr!r} not in error message:\n{msg}"


def test_allowed_triggers_are_private_only() -> None:
    """No sponsor, calendar, or validation code may ever ride a nudge."""
    assert {
        ReasonCode.MISSED_TASK_THRESHOLD_REACHED,
        ReasonCode.CHECKIN_DUE,
        ReasonCode.CHECKIN_MISSED,
        ReasonCode.LOW_COMPLETION_RATE,
        ReasonCode.USER_RECOMMITMENT_REQUIRED,
    } == ALLOWED_NUDGE_REASON_CODES
    assert ReasonCode.SPONSOR_REPORT_PENDING not in ALLOWED_NUDGE_REASON_CODES


def test_no_message_body_field_exists() -> None:
    """Privacy rule: the record stores identifiers and outcome metadata only."""
    fields = set(NudgeRecord.model_fields)
    assert not fields & {"message", "body", "text", "content", "wording"}
