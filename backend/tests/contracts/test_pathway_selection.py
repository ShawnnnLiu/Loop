"""Tests for the ``PathwaySelection`` / ``SlotOverride`` contracts (NP-A)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from agentic_calendar.contracts.pathway_selection import PathwaySelection, SlotOverride
from tests._fixture_loader import iter_invalid, iter_valid

CONTRACT = "pathway_selection"


@pytest.mark.parametrize("fixture", list(iter_valid(CONTRACT)), ids=lambda f: f.name)
def test_valid_fixture_parses(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    selection = PathwaySelection.model_validate(payload)
    assert selection.pathway_id == payload["pathway_id"]


@pytest.mark.parametrize("fixture", list(iter_invalid(CONTRACT)), ids=lambda f: f.name)
def test_invalid_fixture_rejected(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    expected = fixture.expected  # type: ignore[attr-defined]
    with pytest.raises(ValidationError) as exc_info:
        PathwaySelection.model_validate(payload)
    msg = str(exc_info.value)
    for substr in expected["error_substrings"]:
        assert substr in msg, f"expected substring {substr!r} not in:\n{msg}"


def _selection(**overrides: object) -> PathwaySelection:
    base: dict[str, object] = {
        "pathway_id": "ai-integration-engineer",
        "pathway_registry_version": "pathway-registry-v1",
        "selected_at": datetime(2026, 7, 19, 12, 0, tzinfo=UTC),
    }
    base.update(overrides)
    return PathwaySelection.model_validate(base)


def test_slot_overrides_default_empty() -> None:
    assert _selection().slot_overrides == []


def test_naive_selected_at_rejected() -> None:
    with pytest.raises(ValidationError):
        _selection(selected_at=datetime(2026, 7, 19, 12, 0))


def test_override_items_distinct_orgs_allowed() -> None:
    sel = _selection(
        slot_overrides=[
            SlotOverride(item_title="Thing", item_organization="A", slot_id="s1"),
            SlotOverride(item_title="Thing", item_organization="B", slot_id="s2"),
        ]
    )
    assert len(sel.slot_overrides) == 2


def test_duplicate_override_item_rejected() -> None:
    with pytest.raises(ValidationError):
        _selection(
            slot_overrides=[
                SlotOverride(item_title="Thing", item_organization=None, slot_id="s1"),
                SlotOverride(item_title="thing", item_organization=None, slot_id="s2"),
            ]
        )


def test_extra_field_forbidden() -> None:
    with pytest.raises(ValidationError):
        _selection(bogus=1)
