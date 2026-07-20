"""Tests for the ``StrategyConstraints`` contract."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from agentic_calendar.contracts.common_types import Priority
from agentic_calendar.contracts.strategy_constraints import StrategyConstraints
from tests._fixture_loader import iter_invalid, iter_valid


def test_defaults_match_spec() -> None:
    c = StrategyConstraints()
    assert c.max_modules == 12
    assert c.required_priority_values == [Priority.HIGH, Priority.MEDIUM, Priority.LOW]
    assert c.max_total_estimated_minutes == 4800
    assert c.must_reference_claims_for_company_specific_modules is True
    # Story-layer fields (NP-A) default to "no pathway shaping": a profile
    # without a selection produces today's bundle unchanged.
    assert c.pathway_id is None
    assert c.unfilled_slots == []
    assert c.max_slot_modules == 3


def test_unfilled_slots_require_pathway_id() -> None:
    from agentic_calendar.contracts.strategy_constraints import UnfilledSlot

    slot = UnfilledSlot(slot_id="s", title="Slot", gap_module_hint="Build it")
    with pytest.raises(ValidationError):
        StrategyConstraints(unfilled_slots=[slot])
    # With a pathway_id it is valid.
    ok = StrategyConstraints(pathway_id="p", unfilled_slots=[slot])
    assert ok.pathway_id == "p"


def test_duplicate_unfilled_slot_ids_rejected() -> None:
    from agentic_calendar.contracts.strategy_constraints import UnfilledSlot

    with pytest.raises(ValidationError):
        StrategyConstraints(
            pathway_id="p",
            unfilled_slots=[
                UnfilledSlot(slot_id="dup", title="A", gap_module_hint="x"),
                UnfilledSlot(slot_id="dup", title="B", gap_module_hint="y"),
            ],
        )


def test_max_slot_modules_bounds() -> None:
    with pytest.raises(ValidationError):
        StrategyConstraints(max_slot_modules=0)
    with pytest.raises(ValidationError):
        StrategyConstraints(max_slot_modules=11)


def test_duplicate_priority_values_rejected() -> None:
    with pytest.raises(ValidationError):
        StrategyConstraints(required_priority_values=[Priority.HIGH, Priority.HIGH])


def test_empty_priority_values_rejected() -> None:
    with pytest.raises(ValidationError):
        StrategyConstraints(required_priority_values=[])


def test_extra_field_forbidden() -> None:
    with pytest.raises(ValidationError):
        StrategyConstraints(unknown=1)  # type: ignore[call-arg]


@pytest.mark.parametrize("kwargs", [{"max_modules": 0}, {"max_total_estimated_minutes": 0}])
def test_positive_bounds(kwargs: dict[str, int]) -> None:
    with pytest.raises(ValidationError):
        StrategyConstraints(**kwargs)


CONTRACT = "strategy_constraints"


@pytest.mark.parametrize("fixture", list(iter_valid(CONTRACT)), ids=lambda f: f.name)
def test_valid_fixture_parses(fixture: object) -> None:
    obj = StrategyConstraints.model_validate(fixture.payload)  # type: ignore[attr-defined]
    assert isinstance(obj, StrategyConstraints)


@pytest.mark.parametrize("fixture", list(iter_invalid(CONTRACT)), ids=lambda f: f.name)
def test_invalid_fixture_rejected(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    expected = fixture.expected  # type: ignore[attr-defined]
    with pytest.raises(ValidationError) as exc_info:
        StrategyConstraints.model_validate(payload)
    msg = str(exc_info.value)
    for substr in expected["error_substrings"]:
        assert substr in msg, f"expected substring {substr!r} not in:\n{msg}"
