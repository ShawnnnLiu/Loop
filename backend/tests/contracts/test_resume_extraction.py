"""Tests for the ``ResumeExtraction`` contract.

Each fixture under ``tests/fixtures/{valid,invalid}/resume_extraction/``
becomes a parametrized test case. Invalid fixtures declare
``error_substrings`` in their ``.expected.json`` sidecar.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from agentic_calendar.contracts.resume_extraction import ResumeExtraction
from tests._fixture_loader import iter_invalid, iter_valid

CONTRACT = "resume_extraction"


@pytest.mark.parametrize(
    "fixture",
    list(iter_valid(CONTRACT)),
    ids=lambda f: f.name,
)
def test_valid_fixture_parses(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    extraction = ResumeExtraction.model_validate(payload)
    assert extraction.skills == payload.get("skills", [])


@pytest.mark.parametrize(
    "fixture",
    list(iter_invalid(CONTRACT)),
    ids=lambda f: f.name,
)
def test_invalid_fixture_rejected(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    expected = fixture.expected  # type: ignore[attr-defined]
    with pytest.raises(ValidationError) as exc_info:
        ResumeExtraction.model_validate(payload)
    msg = str(exc_info.value)
    for substr in expected["error_substrings"]:
        assert substr in msg, (
            f"expected substring {substr!r} not in error message:\n{msg}"
        )


def test_all_lists_default_empty() -> None:
    extraction = ResumeExtraction.model_validate({})
    assert extraction.experience == []
    assert extraction.skills == []
    assert extraction.known_strengths == []
    assert extraction.inferred_weak_spots == []
    assert extraction.target_company_categories == []


def test_extraction_is_frozen() -> None:
    extraction = ResumeExtraction.model_validate({"skills": ["Python"]})
    with pytest.raises(ValidationError):
        extraction.skills = []  # type: ignore[misc]


def test_unknown_field_rejected() -> None:
    with pytest.raises(ValidationError) as exc_info:
        ResumeExtraction.model_validate({"prerequisites_met": True})
    assert "prerequisites_met" in str(exc_info.value)


def test_duplicate_experience_by_title_and_org_rejected() -> None:
    payload = {
        "experience": [
            {"title": "Backend Engineer", "organization": "Acme Corp"},
            {"title": "backend engineer", "organization": "ACME CORP"},
        ]
    }
    with pytest.raises(ValidationError) as exc_info:
        ResumeExtraction.model_validate(payload)
    assert "unique by (title, organization)" in str(exc_info.value)


def test_same_title_different_org_allowed() -> None:
    payload = {
        "experience": [
            {"title": "Backend Engineer", "organization": "Acme Corp"},
            {"title": "Backend Engineer", "organization": "Initech"},
        ]
    }
    extraction = ResumeExtraction.model_validate(payload)
    assert len(extraction.experience) == 2
