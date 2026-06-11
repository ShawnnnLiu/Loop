"""Tests for ``PowerUserEligibility`` and ``PerUserRefinement``."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from agentic_calendar.contracts.power_user import (
    CRITERION_REASON_CODES,
    EligibilityCriterion,
    PerUserRefinement,
    PowerUserEligibility,
)
from agentic_calendar.contracts.reason_codes import ReasonCode
from tests._fixture_loader import iter_invalid, iter_valid


@pytest.mark.parametrize(
    "fixture",
    list(iter_valid("power_user_eligibility")),
    ids=lambda f: f.name,
)
def test_valid_eligibility_fixture_parses(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    obj = PowerUserEligibility.model_validate(payload)
    assert obj.user_id == payload["user_id"]


@pytest.mark.parametrize(
    "fixture",
    list(iter_invalid("power_user_eligibility")),
    ids=lambda f: f.name,
)
def test_invalid_eligibility_fixture_rejected(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    expected = fixture.expected  # type: ignore[attr-defined]
    with pytest.raises(ValidationError) as exc_info:
        PowerUserEligibility.model_validate(payload)
    msg = str(exc_info.value)
    for substr in expected["error_substrings"]:
        assert substr in msg, (
            f"expected substring {substr!r} not in error message:\n{msg}"
        )


@pytest.mark.parametrize(
    "fixture",
    list(iter_valid("per_user_refinement")),
    ids=lambda f: f.name,
)
def test_valid_refinement_fixture_parses(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    obj = PerUserRefinement.model_validate(payload)
    assert obj.user_id == payload["user_id"]


@pytest.mark.parametrize(
    "fixture",
    list(iter_invalid("per_user_refinement")),
    ids=lambda f: f.name,
)
def test_invalid_refinement_fixture_rejected(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    expected = fixture.expected  # type: ignore[attr-defined]
    with pytest.raises(ValidationError) as exc_info:
        PerUserRefinement.model_validate(payload)
    msg = str(exc_info.value)
    for substr in expected["error_substrings"]:
        assert substr in msg, (
            f"expected substring {substr!r} not in error message:\n{msg}"
        )


def test_every_criterion_has_a_distinct_reason_code() -> None:
    codes = list(CRITERION_REASON_CODES.values())
    assert len(set(codes)) == len(codes) == len(EligibilityCriterion)
    assert set(CRITERION_REASON_CODES) == set(EligibilityCriterion)


def test_unmet_reason_codes_ordered() -> None:
    fixture = next(
        f
        for f in iter_valid("power_user_eligibility")
        if f.name == "ineligible_two_criteria_unmet"
    )
    obj = PowerUserEligibility.model_validate(fixture.payload)
    assert obj.unmet_reason_codes() == (
        ReasonCode.POWER_USER_TOTAL_COMPLETIONS_BELOW_THRESHOLD,
        ReasonCode.POWER_USER_CATEGORY_COMPLETIONS_BELOW_THRESHOLD,
    )
