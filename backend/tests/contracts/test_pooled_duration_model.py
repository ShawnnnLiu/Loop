"""Tests for ``PooledDurationModel``."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from agentic_calendar.contracts.pooled_duration_model import (
    CompletionRateBand,
    MultiplierBand,
    PooledDurationModel,
    TimeOfDayBand,
)
from tests._fixture_loader import iter_invalid, iter_valid

CONTRACT = "pooled_duration_model"


@pytest.mark.parametrize(
    "fixture",
    list(iter_valid(CONTRACT)),
    ids=lambda f: f.name,
)
def test_valid_fixture_parses(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    model = PooledDurationModel.model_validate(payload)
    assert model.model_version == payload["model_version"]


@pytest.mark.parametrize(
    "fixture",
    list(iter_invalid(CONTRACT)),
    ids=lambda f: f.name,
)
def test_invalid_fixture_rejected(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    expected = fixture.expected  # type: ignore[attr-defined]
    with pytest.raises(ValidationError) as exc_info:
        PooledDurationModel.model_validate(payload)
    msg = str(exc_info.value)
    for substr in expected["error_substrings"]:
        assert substr in msg, (
            f"expected substring {substr!r} not in error message:\n{msg}"
        )


def test_content_hash_is_label_and_clock_independent() -> None:
    """Two builds of the same data under different labels share a hash."""
    fixture = next(f for f in iter_valid(CONTRACT) if f.name == "empty_no_data")
    payload = dict(fixture.payload)
    relabeled = payload | {
        "model_version": "another-label",
        "trained_at": "2026-07-01T00:00:00Z",
    }
    a = PooledDurationModel.model_validate(payload)
    b = PooledDurationModel.model_validate(relabeled)
    assert a.content_hash == b.content_hash


def test_band_enums_are_closed() -> None:
    assert {b.value for b in TimeOfDayBand} == {"morning", "afternoon", "evening", "night"}
    assert {b.value for b in CompletionRateBand} == {"low", "medium", "high"}
    assert {b.value for b in MultiplierBand} == {"faster", "baseline", "slower"}
