"""Tests for ``InterventionDecision`` and the policy-table constants."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from agentic_calendar.contracts.accountability_intervention import (
    ACTION_TO_REASON_CODES,
    PRIVATE_LANE_POLICIES,
    SPONSOR_LANE_POLICY,
    AccountabilityAction,
    InterventionDecision,
)
from agentic_calendar.contracts.reason_codes import ReasonCode
from tests._fixture_loader import iter_invalid, iter_valid

CONTRACT = "accountability_intervention"


@pytest.mark.parametrize(
    "fixture",
    list(iter_valid(CONTRACT)),
    ids=lambda f: f.name,
)
def test_valid_fixture_parses(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    decision = InterventionDecision.model_validate(payload)
    assert decision.decision_id == payload["decision_id"]


@pytest.mark.parametrize(
    "fixture",
    list(iter_invalid(CONTRACT)),
    ids=lambda f: f.name,
)
def test_invalid_fixture_rejected(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    expected = fixture.expected  # type: ignore[attr-defined]
    with pytest.raises(ValidationError) as exc_info:
        InterventionDecision.model_validate(payload)
    msg = str(exc_info.value)
    for substr in expected["error_substrings"]:
        assert substr in msg, f"expected substring {substr!r} not in error message:\n{msg}"


def test_policy_table_order_is_axiom_21() -> None:
    """The canonical order is the axiom 21 policy table; tests pin it so a
    reorder is a deliberate spec change, not an accident."""
    assert PRIVATE_LANE_POLICIES == (
        "missed_task_warning",
        "recovery_plan",
        "weekly_checkin_required",
        "scope_reduction",
    )
    assert SPONSOR_LANE_POLICY == "sponsor_summary"


def test_every_private_action_has_reason_codes() -> None:
    private_actions = set(AccountabilityAction) - {
        AccountabilityAction.GENERATE_SPONSOR_SUMMARY_DRAFT
    }
    assert set(ACTION_TO_REASON_CODES) == private_actions
    for codes in ACTION_TO_REASON_CODES.values():
        assert codes, "every action carries at least one reason code"


def test_checkin_action_distinguishes_due_from_missed() -> None:
    codes = ACTION_TO_REASON_CODES[AccountabilityAction.CREATE_WEEKLY_CHECKIN_PROMPT]
    assert codes == {ReasonCode.CHECKIN_DUE, ReasonCode.CHECKIN_MISSED}
