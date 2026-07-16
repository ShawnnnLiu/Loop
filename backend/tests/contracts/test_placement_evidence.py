"""Tests for ``PlacementEvidence`` / ``EvidenceCell``."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from agentic_calendar.contracts.common_types import TaskCategory
from agentic_calendar.contracts.placement_evidence import (
    EvidenceCell,
    EvidenceSource,
    PlacementEvidence,
)
from agentic_calendar.contracts.pooled_duration_model import TimeOfDayBand
from tests._fixture_loader import iter_invalid, iter_valid


@pytest.mark.parametrize(
    "fixture",
    list(iter_valid("placement_evidence")),
    ids=lambda f: f.name,
)
def test_valid_fixture_parses(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    obj = PlacementEvidence.model_validate(payload)
    assert len(obj.cells) == len(payload["cells"])


@pytest.mark.parametrize(
    "fixture",
    list(iter_invalid("placement_evidence")),
    ids=lambda f: f.name,
)
def test_invalid_fixture_rejected(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    expected = fixture.expected  # type: ignore[attr-defined]
    with pytest.raises(ValidationError) as exc_info:
        PlacementEvidence.model_validate(payload)
    msg = str(exc_info.value)
    for substr in expected["error_substrings"]:
        assert substr in msg, (
            f"expected substring {substr!r} not in error message:\n{msg}"
        )


def test_valid_fixtures_round_trip() -> None:
    """model_validate(model_dump()) is the identity for every valid fixture."""
    for fixture in iter_valid("placement_evidence"):
        obj = PlacementEvidence.model_validate(fixture.payload)
        assert PlacementEvidence.model_validate(obj.model_dump(mode="json")) == obj


def test_same_category_band_allowed_across_sources() -> None:
    """Uniqueness is the (category, band, source) triple — a (category, band)
    pair may carry both a pooled and a refined cell (consumers resolve
    precedence, not the contract)."""
    evidence = PlacementEvidence(
        cells=[
            EvidenceCell(
                category=TaskCategory.PRACTICE,
                time_of_day_band=TimeOfDayBand.EVENING,
                multiplier=0.85,
                weighted_sample=12.0,
                source=EvidenceSource.POOLED,
            ),
            EvidenceCell(
                category=TaskCategory.PRACTICE,
                time_of_day_band=TimeOfDayBand.EVENING,
                multiplier=0.8,
                weighted_sample=6.0,
                source=EvidenceSource.PER_USER_REFINED,
            ),
        ]
    )
    assert len(evidence.cells) == 2


def test_refined_cell_requires_multiplier_too() -> None:
    with pytest.raises(ValidationError, match="requires a multiplier"):
        EvidenceCell(
            category=TaskCategory.PRACTICE,
            time_of_day_band=TimeOfDayBand.EVENING,
            multiplier=None,
            weighted_sample=6.0,
            source=EvidenceSource.PER_USER_REFINED,
        )


def test_default_evidence_is_empty() -> None:
    assert PlacementEvidence().cells == []
