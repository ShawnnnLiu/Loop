"""Tests for ``SyllabusUnits`` and ``SyllabusModule``."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from agentic_calendar.contracts.syllabus_units import SyllabusUnits
from tests._fixture_loader import iter_invalid, iter_valid

CONTRACT = "syllabus_units"


@pytest.mark.parametrize(
    "fixture",
    list(iter_valid(CONTRACT)),
    ids=lambda f: f.name,
)
def test_valid_fixture_parses(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    syl = SyllabusUnits.model_validate(payload)
    assert syl.syllabus_version == payload["syllabus_version"]
    assert len(syl.modules) == len(payload["modules"])


@pytest.mark.parametrize(
    "fixture",
    list(iter_invalid(CONTRACT)),
    ids=lambda f: f.name,
)
def test_invalid_fixture_rejected(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    expected = fixture.expected  # type: ignore[attr-defined]
    with pytest.raises(ValidationError) as exc_info:
        SyllabusUnits.model_validate(payload)
    msg = str(exc_info.value)
    for substr in expected["error_substrings"]:
        assert substr in msg, (
            f"expected substring {substr!r} not in error message:\n{msg}"
        )


def test_empty_modules_rejected() -> None:
    with pytest.raises(ValidationError):
        SyllabusUnits.model_validate(
            {"syllabus_version": "v1", "goal_summary": "g", "modules": []}
        )
