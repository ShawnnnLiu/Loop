"""Tests for the ``StrategistInput`` contract."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from agentic_calendar.contracts.source_claim import SourceClaim
from agentic_calendar.contracts.strategist_input import StrategistInput
from agentic_calendar.contracts.strategy_constraints import StrategyConstraints
from agentic_calendar.contracts.user_profile import UserProfile
from tests._fixture_loader import iter_valid


def _profile() -> UserProfile:
    return UserProfile.model_validate(next(iter_valid("user_profile")).payload)


def _claim(claim_id: str) -> SourceClaim:
    payload = dict(next(iter_valid("source_claim")).payload)
    payload["claim_id"] = claim_id
    return SourceClaim.model_validate(payload)


def test_defaults_applied() -> None:
    bundle = StrategistInput(user_profile=_profile())
    assert bundle.source_claims == []
    assert isinstance(bundle.strategy_constraints, StrategyConstraints)


def test_accepts_claims() -> None:
    bundle = StrategistInput(
        user_profile=_profile(), source_claims=[_claim("a"), _claim("b")]
    )
    assert [c.claim_id for c in bundle.source_claims] == ["a", "b"]


def test_duplicate_claim_ids_rejected() -> None:
    with pytest.raises(ValidationError):
        StrategistInput(user_profile=_profile(), source_claims=[_claim("dup"), _claim("dup")])


def test_extra_field_forbidden() -> None:
    with pytest.raises(ValidationError):
        StrategistInput(user_profile=_profile(), bogus=1)  # type: ignore[call-arg]
