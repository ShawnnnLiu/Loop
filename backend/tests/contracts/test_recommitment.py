"""Tests for ``RecommitmentRequest`` / ``RecommitmentEvent``."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from agentic_calendar.contracts.recommitment import (
    RecommitmentEvent,
    RecommitmentRequest,
)
from tests._fixture_loader import iter_invalid, iter_valid


@pytest.mark.parametrize(
    "fixture",
    list(iter_valid("recommitment_request")),
    ids=lambda f: f.name,
)
def test_valid_request_parses(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    request = RecommitmentRequest.model_validate(payload)
    assert request.recommitment_request_id == payload["recommitment_request_id"]


@pytest.mark.parametrize(
    "fixture",
    list(iter_invalid("recommitment_request")),
    ids=lambda f: f.name,
)
def test_invalid_request_rejected(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    expected = fixture.expected  # type: ignore[attr-defined]
    with pytest.raises(ValidationError) as exc_info:
        RecommitmentRequest.model_validate(payload)
    msg = str(exc_info.value)
    for substr in expected["error_substrings"]:
        assert substr in msg, f"expected substring {substr!r} not in error message:\n{msg}"


@pytest.mark.parametrize(
    "fixture",
    list(iter_valid("recommitment_event")),
    ids=lambda f: f.name,
)
def test_valid_event_parses(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    event = RecommitmentEvent.model_validate(payload)
    assert event.recommitment_event_id == payload["recommitment_event_id"]


@pytest.mark.parametrize(
    "fixture",
    list(iter_invalid("recommitment_event")),
    ids=lambda f: f.name,
)
def test_invalid_event_rejected(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    expected = fixture.expected  # type: ignore[attr-defined]
    with pytest.raises(ValidationError) as exc_info:
        RecommitmentEvent.model_validate(payload)
    msg = str(exc_info.value)
    for substr in expected["error_substrings"]:
        assert substr in msg, f"expected substring {substr!r} not in error message:\n{msg}"
