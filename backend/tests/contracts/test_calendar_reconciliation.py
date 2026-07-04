"""Tests for the ``calendar_reconciliation`` result / delta contract."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from agentic_calendar.contracts.calendar_reconciliation import (
    ADJUSTMENT_REASON_CODES,
    CalendarReconciliationResult,
)
from agentic_calendar.contracts.reason_codes import ReasonCode
from tests._fixture_loader import iter_invalid, iter_valid

CONTRACT = "calendar_reconciliation"


@pytest.mark.parametrize("fixture", list(iter_valid(CONTRACT)), ids=lambda f: f.name)
def test_valid_fixture_parses(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    result = CalendarReconciliationResult.model_validate(payload)
    assert result.run_id == payload["run_id"]


@pytest.mark.parametrize("fixture", list(iter_invalid(CONTRACT)), ids=lambda f: f.name)
def test_invalid_fixture_rejected(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    expected = fixture.expected  # type: ignore[attr-defined]
    with pytest.raises(ValidationError) as exc_info:
        CalendarReconciliationResult.model_validate(payload)
    msg = str(exc_info.value)
    for substr in expected["error_substrings"]:
        assert substr in msg, f"expected substring {substr!r} not in error message:\n{msg}"


def test_adjustment_reason_codes_are_the_three_hard_placement_codes() -> None:
    """A rejected reconciliation delta reuses exactly the drag-to-adjust HARD
    rules. Prerequisite ordering is advisory (``DEPENDENCY_ADVISORY``) and never
    rejects an external move (ADR-0008), so it is not in this set."""
    expected = {
        ReasonCode.NO_VALID_CONTIGUOUS_BLOCK,
        ReasonCode.OUTSIDE_ALLOWED_HOURS,
        ReasonCode.DAILY_LOAD_EXCEEDED,
    }
    assert expected == ADJUSTMENT_REASON_CODES
    assert ReasonCode.DEPENDENCY_BLOCKED not in ADJUSTMENT_REASON_CODES
    assert ReasonCode.DEPENDENCY_ADVISORY not in ADJUSTMENT_REASON_CODES
