"""Tests for ``DriftEvent``, ``DriftEvidence``, and related types."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from agentic_calendar.contracts.drift_event import (
    DRIFT_TYPE_TO_REASON_CODE,
    DriftEvent,
    DriftType,
)
from tests._fixture_loader import iter_invalid, iter_valid

CONTRACT = "drift_event"


@pytest.mark.parametrize(
    "fixture",
    list(iter_valid(CONTRACT)),
    ids=lambda f: f.name,
)
def test_valid_fixture_parses(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    event = DriftEvent.model_validate(payload)
    assert event.drift_event_id == payload["drift_event_id"]


@pytest.mark.parametrize(
    "fixture",
    list(iter_invalid(CONTRACT)),
    ids=lambda f: f.name,
)
def test_invalid_fixture_rejected(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    expected = fixture.expected  # type: ignore[attr-defined]
    with pytest.raises(ValidationError) as exc_info:
        DriftEvent.model_validate(payload)
    msg = str(exc_info.value)
    for substr in expected["error_substrings"]:
        assert substr in msg, (
            f"expected substring {substr!r} not in error message:\n{msg}"
        )


def test_drift_type_to_reason_code_mapping_complete() -> None:
    """Every DriftType has a corresponding entry in DRIFT_TYPE_TO_REASON_CODE."""
    for drift_type in DriftType:
        assert drift_type in DRIFT_TYPE_TO_REASON_CODE, (
            f"{drift_type!r} missing from DRIFT_TYPE_TO_REASON_CODE"
        )


def test_reason_code_family_is_drift() -> None:
    """Every mapped reason code is in the DRIFT_* family."""
    for drift_type, reason_code in DRIFT_TYPE_TO_REASON_CODE.items():
        assert reason_code.value.startswith("DRIFT_"), (
            f"{drift_type!r} maps to non-DRIFT reason_code {reason_code!r}"
        )
