"""Tests for the ``SkillGrouping`` contract (KT-A)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from agentic_calendar.contracts.skill_grouping import (
    SkillGroup,
    SkillGrouping,
    SkillGroupingEntry,
)
from tests._fixture_loader import iter_invalid, iter_valid

CONTRACT = "skill_grouping"


@pytest.mark.parametrize("fixture", list(iter_valid(CONTRACT)), ids=lambda f: f.name)
def test_valid_fixture_parses(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    grouping = SkillGrouping.model_validate(payload)
    assert len(grouping.entries) == len(payload["entries"])


@pytest.mark.parametrize("fixture", list(iter_invalid(CONTRACT)), ids=lambda f: f.name)
def test_invalid_fixture_rejected(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    expected = fixture.expected  # type: ignore[attr-defined]
    with pytest.raises(ValidationError) as exc_info:
        SkillGrouping.model_validate(payload)
    msg = str(exc_info.value)
    for substr in expected["error_substrings"]:
        assert substr in msg, f"expected substring {substr!r} not in:\n{msg}"


def _grouping(**overrides: object) -> SkillGrouping:
    base: dict[str, object] = {
        "skill_grouping_version": "skill-grouping-v1",
        "taxonomy_version": "skill-taxonomy-v4",
        "groups": [SkillGroup(group_id="kg-a", title="A", blurb="b")],
        "entries": [
            SkillGroupingEntry(
                skill_id="skill.rag",
                group_id="kg-a",
                expected_minutes=360,
                blurb="b",
            )
        ],
    }
    base.update(overrides)
    return SkillGrouping.model_validate(base)


def test_expected_minutes_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        SkillGroupingEntry(
            skill_id="skill.rag", group_id="kg-a", expected_minutes=0, blurb="b"
        )


def test_group_id_pattern_enforced() -> None:
    with pytest.raises(ValidationError):
        SkillGroup(group_id="retrieval", title="A", blurb="b")


def test_empty_groups_rejected() -> None:
    with pytest.raises(ValidationError):
        _grouping(groups=[])


def test_empty_entries_rejected() -> None:
    with pytest.raises(ValidationError):
        _grouping(entries=[])


def test_grouping_extra_field_forbidden() -> None:
    with pytest.raises(ValidationError):
        SkillGrouping.model_validate(
            {
                "skill_grouping_version": "v1",
                "taxonomy_version": "t1",
                "groups": [{"group_id": "kg-a", "title": "A", "blurb": "b"}],
                "entries": [
                    {
                        "skill_id": "skill.rag",
                        "group_id": "kg-a",
                        "expected_minutes": 360,
                        "blurb": "b",
                    }
                ],
                "bogus": 1,
            }
        )
