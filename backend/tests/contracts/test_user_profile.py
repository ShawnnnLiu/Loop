"""Tests for the ``UserProfile`` contract.

Each fixture under ``tests/fixtures/{valid,invalid}/user_profile/`` becomes a
parametrized test case. Invalid fixtures must declare ``error_substrings`` in
their ``.expected.json`` sidecar so we assert against structured expectations
rather than free-form prose.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from agentic_calendar.contracts.user_profile import UserProfile
from tests._fixture_loader import iter_invalid, iter_valid

CONTRACT = "user_profile"


@pytest.mark.parametrize(
    "fixture",
    list(iter_valid(CONTRACT)),
    ids=lambda f: f.name,
)
def test_valid_fixture_parses(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    profile = UserProfile.model_validate(payload)
    assert profile.user_id == payload["user_id"]


@pytest.mark.parametrize(
    "fixture",
    list(iter_invalid(CONTRACT)),
    ids=lambda f: f.name,
)
def test_invalid_fixture_rejected(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    expected = fixture.expected  # type: ignore[attr-defined]
    with pytest.raises(ValidationError) as exc_info:
        UserProfile.model_validate(payload)
    msg = str(exc_info.value)
    for substr in expected["error_substrings"]:
        assert substr in msg, (
            f"expected substring {substr!r} not in error message:\n{msg}"
        )


def test_profile_is_frozen() -> None:
    payload = next(iter_valid(CONTRACT)).payload
    profile = UserProfile.model_validate(payload)
    with pytest.raises(ValidationError):
        profile.weekly_hours = 99  # type: ignore[misc]


def test_unknown_field_rejected() -> None:
    payload = next(iter_valid(CONTRACT)).payload | {"snowflake_field": True}
    with pytest.raises(ValidationError) as exc_info:
        UserProfile.model_validate(payload)
    assert "snowflake_field" in str(exc_info.value)
