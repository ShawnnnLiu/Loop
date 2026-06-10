"""Tests for ``AccountabilityState``."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from agentic_calendar.contracts.accountability_state import AccountabilityState
from tests._fixture_loader import iter_invalid, iter_valid

CONTRACT = "accountability_state"


@pytest.mark.parametrize(
    "fixture",
    list(iter_valid(CONTRACT)),
    ids=lambda f: f.name,
)
def test_valid_fixture_parses(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    state = AccountabilityState.model_validate(payload)
    assert state.user_id == payload["user_id"]


@pytest.mark.parametrize(
    "fixture",
    list(iter_invalid(CONTRACT)),
    ids=lambda f: f.name,
)
def test_invalid_fixture_rejected(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    expected = fixture.expected  # type: ignore[attr-defined]
    with pytest.raises(ValidationError) as exc_info:
        AccountabilityState.model_validate(payload)
    msg = str(exc_info.value)
    for substr in expected["error_substrings"]:
        assert substr in msg, f"expected substring {substr!r} not in error message:\n{msg}"


def test_state_is_frozen() -> None:
    """Axiom 21: the state is recomputed, never edited in place."""
    payloads = {f.name: f.payload for f in iter_valid(CONTRACT)}
    state = AccountabilityState.model_validate(payloads["slightly_behind"])
    with pytest.raises(ValidationError):
        state.missed_tasks_7d = 0  # type: ignore[misc]
