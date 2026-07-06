"""Tests for the ``ResumeIntakeInput`` contract.

Each fixture under ``tests/fixtures/{valid,invalid}/resume_intake_input/``
becomes a parametrized test case. Invalid fixtures declare
``error_substrings`` in their ``.expected.json`` sidecar.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from agentic_calendar.contracts.resume_intake_input import (
    RESUME_TEXT_MAX_CHARS,
    RESUME_TEXT_MIN_CHARS,
    DraftProfileContext,
    ResumeIntakeInput,
)
from tests._fixture_loader import iter_invalid, iter_valid

CONTRACT = "resume_intake_input"


@pytest.mark.parametrize(
    "fixture",
    list(iter_valid(CONTRACT)),
    ids=lambda f: f.name,
)
def test_valid_fixture_parses(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    bundle = ResumeIntakeInput.model_validate(payload)
    assert bundle.user_id == payload["user_id"]


@pytest.mark.parametrize(
    "fixture",
    list(iter_invalid(CONTRACT)),
    ids=lambda f: f.name,
)
def test_invalid_fixture_rejected(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    expected = fixture.expected  # type: ignore[attr-defined]
    with pytest.raises(ValidationError) as exc_info:
        ResumeIntakeInput.model_validate(payload)
    msg = str(exc_info.value)
    for substr in expected["error_substrings"]:
        assert substr in msg, (
            f"expected substring {substr!r} not in error message:\n{msg}"
        )


def test_draft_context_defaults_to_all_none() -> None:
    context = DraftProfileContext()
    assert context.goal is None
    assert context.target_role is None
    assert context.experience_level is None
    assert context.timeline_weeks is None
    assert context.weekly_hours is None


def test_resume_text_bounds_are_inclusive() -> None:
    ResumeIntakeInput(user_id="u", resume_text="x" * RESUME_TEXT_MIN_CHARS)
    ResumeIntakeInput(user_id="u", resume_text="x" * RESUME_TEXT_MAX_CHARS)
    with pytest.raises(ValidationError):
        ResumeIntakeInput(user_id="u", resume_text="x" * (RESUME_TEXT_MIN_CHARS - 1))
    with pytest.raises(ValidationError):
        ResumeIntakeInput(user_id="u", resume_text="x" * (RESUME_TEXT_MAX_CHARS + 1))


def test_input_is_frozen() -> None:
    bundle = ResumeIntakeInput(user_id="u", resume_text="x" * RESUME_TEXT_MIN_CHARS)
    with pytest.raises(ValidationError):
        bundle.user_id = "other"  # type: ignore[misc]


def test_unknown_field_rejected() -> None:
    with pytest.raises(ValidationError) as exc_info:
        ResumeIntakeInput.model_validate(
            {
                "user_id": "u",
                "resume_text": "x" * RESUME_TEXT_MIN_CHARS,
                "run_id": "intake-123",
            }
        )
    assert "run_id" in str(exc_info.value)
