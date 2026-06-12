"""Tests for ``ThresholdChange`` (``threshold-change-log.schema.md``)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from agentic_calendar.contracts.threshold_change_log import ThresholdChange
from tests._fixture_loader import iter_invalid, iter_valid

CONTRACT = "threshold_change_log"


@pytest.mark.parametrize(
    "fixture",
    list(iter_valid(CONTRACT)),
    ids=lambda f: f.name,
)
def test_valid_fixture_parses(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    change = ThresholdChange.model_validate(payload)
    assert change.change_id == payload["change_id"]


@pytest.mark.parametrize(
    "fixture",
    list(iter_invalid(CONTRACT)),
    ids=lambda f: f.name,
)
def test_invalid_fixture_rejected(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    expected = fixture.expected  # type: ignore[attr-defined]
    with pytest.raises(ValidationError) as exc_info:
        ThresholdChange.model_validate(payload)
    msg = str(exc_info.value)
    for substr in expected["error_substrings"]:
        assert substr in msg, (
            f"expected substring {substr!r} not in error message:\n{msg}"
        )


def test_int_and_float_values_preserve_their_types() -> None:
    """Strict number union keeps an int an int — the journal must replay the
    exact value the loader recorded, not a coerced float."""
    int_change = ThresholdChange.model_validate(
        next(f for f in iter_valid(CONTRACT) if f.name == "int_change").payload
    )
    assert isinstance(int_change.new_value, int)
    float_change = ThresholdChange.model_validate(
        next(f for f in iter_valid(CONTRACT) if f.name == "float_change").payload
    )
    assert isinstance(float_change.new_value, float)


def test_numerically_equal_int_and_float_rejected() -> None:
    """``1`` → ``1.0`` is a no-op, not a change (spec: numeric comparison)."""
    payload = next(f for f in iter_valid(CONTRACT) if f.name == "int_change").payload
    with pytest.raises(ValidationError, match="new_value must differ from prior_value"):
        ThresholdChange.model_validate(
            dict(payload) | {"prior_value": 4, "new_value": 4.0}
        )


def test_uppercase_section_rejected() -> None:
    """Section/field names are shape-checked against ``^[a-z][a-z0-9_]*$``."""
    payload = dict(next(f for f in iter_valid(CONTRACT) if f.name == "int_change").payload)
    payload["config_section"] = "DriftThresholds"
    with pytest.raises(ValidationError, match="String should match pattern"):
        ThresholdChange.model_validate(payload)
