"""Tests for ``AccountabilityContract``."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from agentic_calendar.contracts.accountability_contract import AccountabilityContract
from tests._fixture_loader import iter_invalid, iter_valid

CONTRACT = "accountability_contract"


@pytest.mark.parametrize(
    "fixture",
    list(iter_valid(CONTRACT)),
    ids=lambda f: f.name,
)
def test_valid_fixture_parses(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    contract = AccountabilityContract.model_validate(payload)
    assert contract.contract_id == payload["contract_id"]


@pytest.mark.parametrize(
    "fixture",
    list(iter_invalid(CONTRACT)),
    ids=lambda f: f.name,
)
def test_invalid_fixture_rejected(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    expected = fixture.expected  # type: ignore[attr-defined]
    with pytest.raises(ValidationError) as exc_info:
        AccountabilityContract.model_validate(payload)
    msg = str(exc_info.value)
    for substr in expected["error_substrings"]:
        assert substr in msg, f"expected substring {substr!r} not in error message:\n{msg}"


def test_inactive_contract_keeps_snapshot() -> None:
    """An inactive contract still carries a full, valid snapshot.

    Scenario 24 needs the contract object itself to stay valid when disabled —
    the kill switch is ``active``, not a degraded shape.
    """
    payloads = {f.name: f.payload for f in iter_valid(CONTRACT)}
    inactive = AccountabilityContract.model_validate(payloads["inactive_sponsor_enabled"])
    assert inactive.active is False
    assert inactive.sponsor_reporting_allowed is True
    assert inactive.profile_version == "mot_v3"
