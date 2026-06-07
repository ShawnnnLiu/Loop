"""Tests for the ``Milestone`` / ``MilestoneTemplate`` contracts (Phase 5c)."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from agentic_calendar.contracts.common_types import Priority
from agentic_calendar.contracts.milestone_template import (
    GoalClass,
    Milestone,
    MilestoneTemplate,
)
from tests._fixture_loader import iter_invalid, iter_valid

CONTRACT = "milestone_template"


@pytest.mark.parametrize("fixture", list(iter_valid(CONTRACT)), ids=lambda f: f.name)
def test_valid_fixture_parses(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    template = MilestoneTemplate.model_validate(payload)
    assert template.template_id == payload["template_id"]


@pytest.mark.parametrize("fixture", list(iter_invalid(CONTRACT)), ids=lambda f: f.name)
def test_invalid_fixture_rejected(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    expected = fixture.expected  # type: ignore[attr-defined]
    with pytest.raises(ValidationError) as exc_info:
        MilestoneTemplate.model_validate(payload)
    msg = str(exc_info.value)
    for substr in expected["error_substrings"]:
        assert substr in msg, f"expected substring {substr!r} not in:\n{msg}"


def _milestone(**overrides: Any) -> Milestone:
    base: dict[str, Any] = {
        "milestone_id": "m1",
        "title": "Title",
        "offset_days_before_deadline": 30,
        "target_outcomes": ["Outcome"],
        "priority": Priority.HIGH,
        "default_estimated_total_min": 120,
    }
    base.update(overrides)
    return Milestone(**base)


def test_zero_offset_allowed() -> None:
    """``offset_days_before_deadline`` is inclusive at 0 (same-day milestone)."""
    assert _milestone(offset_days_before_deadline=0).offset_days_before_deadline == 0


def test_milestone_extra_field_forbidden() -> None:
    with pytest.raises(ValidationError):
        _milestone(bogus=1)


def test_template_extra_field_forbidden() -> None:
    with pytest.raises(ValidationError):
        MilestoneTemplate(
            template_id="t",
            goal_class=GoalClass.CAREER_TRANSITION,
            template_schema_version="v1",
            milestones=[_milestone()],
            bogus=1,  # type: ignore[call-arg]
        )
