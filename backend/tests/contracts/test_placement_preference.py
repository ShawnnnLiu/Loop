"""Tests for ``PlacementPreferenceObservation``."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from agentic_calendar.contracts.placement_preference import (
    PlacementPreferenceObservation,
)
from tests._fixture_loader import iter_invalid, iter_valid


@pytest.mark.parametrize(
    "fixture",
    list(iter_valid("placement_preference")),
    ids=lambda f: f.name,
)
def test_valid_fixture_parses(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    obj = PlacementPreferenceObservation.model_validate(payload)
    assert obj.observation_id == payload["observation_id"]


@pytest.mark.parametrize(
    "fixture",
    list(iter_invalid("placement_preference")),
    ids=lambda f: f.name,
)
def test_invalid_fixture_rejected(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    expected = fixture.expected  # type: ignore[attr-defined]
    with pytest.raises(ValidationError) as exc_info:
        PlacementPreferenceObservation.model_validate(payload)
    msg = str(exc_info.value)
    for substr in expected["error_substrings"]:
        assert substr in msg, (
            f"expected substring {substr!r} not in error message:\n{msg}"
        )


def test_valid_fixtures_round_trip() -> None:
    """model_validate(model_dump()) is the identity for every valid fixture."""
    for fixture in iter_valid("placement_preference"):
        obj = PlacementPreferenceObservation.model_validate(fixture.payload)
        assert (
            PlacementPreferenceObservation.model_validate(obj.model_dump(mode="json"))
            == obj
        )
