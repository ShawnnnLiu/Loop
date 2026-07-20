"""Tests for the ``PathwayTemplate`` / ``EvidenceSlot`` contracts (NP-A)."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from agentic_calendar.contracts.career_track import CareerTrack
from agentic_calendar.contracts.common_types import EvidenceKind
from agentic_calendar.contracts.pathway_template import EvidenceSlot, PathwayTemplate
from tests._fixture_loader import iter_invalid, iter_valid

CONTRACT = "pathway_template"


@pytest.mark.parametrize("fixture", list(iter_valid(CONTRACT)), ids=lambda f: f.name)
def test_valid_fixture_parses(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    template = PathwayTemplate.model_validate(payload)
    assert template.pathway_id == payload["pathway_id"]
    assert len(template.evidence_slots) == len(payload["evidence_slots"])


@pytest.mark.parametrize("fixture", list(iter_invalid(CONTRACT)), ids=lambda f: f.name)
def test_invalid_fixture_rejected(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    expected = fixture.expected  # type: ignore[attr-defined]
    with pytest.raises(ValidationError) as exc_info:
        PathwayTemplate.model_validate(payload)
    msg = str(exc_info.value)
    for substr in expected["error_substrings"]:
        assert substr in msg, f"expected substring {substr!r} not in:\n{msg}"


def _slot(**overrides: Any) -> EvidenceSlot:
    base: dict[str, Any] = {
        "slot_id": "s1",
        "title": "Slot",
        "required_kinds": [EvidenceKind.PROJECT],
        "required_themes_any": ["applied-ml"],
        "min_items": 1,
        "gap_module_hint": "Build a thing",
        "branch_skill_ids": ["skill.a"],
    }
    base.update(overrides)
    return EvidenceSlot(**base)


def test_min_items_defaults_to_one() -> None:
    assert _slot().min_items == 1


def test_min_items_zero_rejected() -> None:
    with pytest.raises(ValidationError):
        _slot(min_items=0)


def test_empty_required_kinds_rejected() -> None:
    with pytest.raises(ValidationError):
        _slot(required_kinds=[])


def test_duplicate_required_themes_rejected() -> None:
    with pytest.raises(ValidationError):
        _slot(required_themes_any=["applied-ml", "Applied-ML"])


def test_duplicate_branch_skill_ids_rejected() -> None:
    with pytest.raises(ValidationError):
        _slot(branch_skill_ids=["skill.a", "skill.a"])


def test_slot_extra_field_forbidden() -> None:
    with pytest.raises(ValidationError):
        _slot(bogus=1)


def test_template_extra_field_forbidden() -> None:
    with pytest.raises(ValidationError):
        PathwayTemplate(
            pathway_id="p",
            pathway_schema_version="v1",
            career_track=CareerTrack.SWE,
            display_name="P",
            spine="s",
            audience_note="a",
            evidence_slots=[_slot()],
            bogus=1,  # type: ignore[call-arg]
        )
