"""Tests for ``UserDurationMultipliers`` and ``CategoryMultiplier``."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from agentic_calendar.contracts.common_types import TaskCategory
from agentic_calendar.contracts.user_duration_multipliers import (
    UserDurationMultipliers,
)
from tests._fixture_loader import iter_invalid, iter_valid

CONTRACT = "user_duration_multipliers"


@pytest.mark.parametrize(
    "fixture",
    list(iter_valid(CONTRACT)),
    ids=lambda f: f.name,
)
def test_valid_fixture_parses(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    udm = UserDurationMultipliers.model_validate(payload)
    assert udm.user_id == payload["user_id"]


@pytest.mark.parametrize(
    "fixture",
    list(iter_invalid(CONTRACT)),
    ids=lambda f: f.name,
)
def test_invalid_fixture_rejected(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    expected = fixture.expected  # type: ignore[attr-defined]
    with pytest.raises(ValidationError) as exc_info:
        UserDurationMultipliers.model_validate(payload)
    msg = str(exc_info.value)
    for substr in expected["error_substrings"]:
        assert substr in msg, (
            f"expected substring {substr!r} not in error message:\n{msg}"
        )


def test_as_map_returns_correct_mapping() -> None:
    """as_map() returns {category: multiplier} keyed by TaskCategory."""
    payload = {
        "user_id": "user_map_test",
        "computed_at": "2026-05-10T08:00:00-07:00",
        "multipliers": [
            {"category": "practice", "multiplier": 1.35, "sample_size": 10, "observed_ratio": 1.35},
            {"category": "concept_review", "multiplier": 0.90, "sample_size": 6, "observed_ratio": 0.90},
        ],
    }
    udm = UserDurationMultipliers.model_validate(payload)
    mapping = udm.as_map()
    assert mapping[TaskCategory.PRACTICE] == 1.35
    assert mapping[TaskCategory.CONCEPT_REVIEW] == 0.90
    assert len(mapping) == 2


def test_empty_multipliers_as_map_is_empty() -> None:
    """as_map() on an empty multipliers list returns {}."""
    payload = {
        "user_id": "user_empty",
        "computed_at": "2026-05-10T08:00:00-07:00",
        "multipliers": [],
    }
    udm = UserDurationMultipliers.model_validate(payload)
    assert udm.as_map() == {}
