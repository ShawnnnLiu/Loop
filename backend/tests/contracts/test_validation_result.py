"""Tests for ``ValidationResult``."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from agentic_calendar.contracts.validation_result import (
    MAX_REPAIR_ATTEMPTS_LLM,
    ValidationResult,
)
from tests._fixture_loader import iter_invalid, iter_valid

CONTRACT = "validation_result"


@pytest.mark.parametrize(
    "fixture",
    list(iter_valid(CONTRACT)),
    ids=lambda f: f.name,
)
def test_valid_fixture_parses(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    result = ValidationResult.model_validate(payload)
    assert result.run_id == payload["run_id"]


@pytest.mark.parametrize(
    "fixture",
    list(iter_invalid(CONTRACT)),
    ids=lambda f: f.name,
)
def test_invalid_fixture_rejected(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    expected = fixture.expected  # type: ignore[attr-defined]
    with pytest.raises(ValidationError) as exc_info:
        ValidationResult.model_validate(payload)
    msg = str(exc_info.value)
    for substr in expected["error_substrings"]:
        assert substr in msg, (
            f"expected substring {substr!r} not in error message:\n{msg}"
        )


def test_repair_cap_constant() -> None:
    assert MAX_REPAIR_ATTEMPTS_LLM == 2
