"""Tests for the ``UserProfile`` contract.

Each fixture under ``tests/fixtures/{valid,invalid}/user_profile/`` becomes a
parametrized test case. Invalid fixtures must declare ``error_substrings`` in
their ``.expected.json`` sidecar so we assert against structured expectations
rather than free-form prose.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from agentic_calendar.contracts.user_profile import (
    PLAN_DIRECTION_MAX_CHARS,
    UserProfile,
)
from tests._fixture_loader import iter_invalid, iter_valid

CONTRACT = "user_profile"


@pytest.mark.parametrize(
    "fixture",
    list(iter_valid(CONTRACT)),
    ids=lambda f: f.name,
)
def test_valid_fixture_parses(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    profile = UserProfile.model_validate(payload)
    assert profile.user_id == payload["user_id"]


@pytest.mark.parametrize(
    "fixture",
    list(iter_invalid(CONTRACT)),
    ids=lambda f: f.name,
)
def test_invalid_fixture_rejected(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    expected = fixture.expected  # type: ignore[attr-defined]
    with pytest.raises(ValidationError) as exc_info:
        UserProfile.model_validate(payload)
    msg = str(exc_info.value)
    for substr in expected["error_substrings"]:
        assert substr in msg, (
            f"expected substring {substr!r} not in error message:\n{msg}"
        )


def test_profile_is_frozen() -> None:
    payload = next(iter_valid(CONTRACT)).payload
    profile = UserProfile.model_validate(payload)
    with pytest.raises(ValidationError):
        profile.weekly_hours = 99  # type: ignore[misc]


def test_unknown_field_rejected() -> None:
    payload = next(iter_valid(CONTRACT)).payload | {"snowflake_field": True}
    with pytest.raises(ValidationError) as exc_info:
        UserProfile.model_validate(payload)
    assert "snowflake_field" in str(exc_info.value)


def test_experience_and_skills_default_empty() -> None:
    payload = {
        k: v
        for k, v in next(iter_valid(CONTRACT)).payload.items()
        if k not in ("experience", "skills")
    }
    profile = UserProfile.model_validate(payload)
    assert profile.experience == []
    assert profile.skills == []


def test_evidence_defaults_and_pathway_selection_optional() -> None:
    """``kind`` defaults to ``work``, ``theme_tags`` to empty, and
    ``pathway_selection`` is absent unless the user chose one (NP-A)."""
    from agentic_calendar.contracts.common_types import EvidenceKind

    payload = {
        k: v
        for k, v in next(iter_valid(CONTRACT)).payload.items()
        if k not in ("experience", "pathway_selection")
    }
    payload["experience"] = [{"title": "A thing I did"}]
    profile = UserProfile.model_validate(payload)
    assert profile.experience[0].kind is EvidenceKind.WORK
    assert profile.experience[0].theme_tags == []
    assert profile.pathway_selection is None


def test_pathway_selection_round_trips() -> None:
    payload = next(iter_valid(CONTRACT)).payload
    profile = UserProfile.model_validate(
        {
            **payload,
            "pathway_selection": {
                "pathway_id": "ai-integration-engineer",
                "pathway_registry_version": "pathway-registry-v1",
                "selected_at": "2026-07-19T12:00:00-07:00",
            },
        }
    )
    assert profile.pathway_selection is not None
    assert profile.pathway_selection.pathway_id == "ai-integration-engineer"


def test_plan_direction_defaults_to_none() -> None:
    payload = {
        k: v
        for k, v in next(iter_valid(CONTRACT)).payload.items()
        if k != "plan_direction"
    }
    profile = UserProfile.model_validate(payload)
    assert profile.plan_direction is None


def test_plan_direction_length_bounds() -> None:
    payload = next(iter_valid(CONTRACT)).payload
    assert UserProfile.model_validate({**payload, "plan_direction": "x"}).plan_direction == "x"
    at_cap = "x" * PLAN_DIRECTION_MAX_CHARS
    assert (
        UserProfile.model_validate({**payload, "plan_direction": at_cap}).plan_direction
        == at_cap
    )
    with pytest.raises(ValidationError):
        UserProfile.model_validate(
            {**payload, "plan_direction": "x" * (PLAN_DIRECTION_MAX_CHARS + 1)}
        )
    # Absent must be null, never "" — min_length=1 rejects the empty string.
    with pytest.raises(ValidationError):
        UserProfile.model_validate({**payload, "plan_direction": ""})


def test_plan_direction_rejects_control_chars_but_keeps_whitespace() -> None:
    payload = next(iter_valid(CONTRACT)).payload
    ok = UserProfile.model_validate(
        {**payload, "plan_direction": "line one\nline two\tend\r"}
    )
    assert ok.plan_direction == "line one\nline two\tend\r"
    for bad, codepoint in (("\x00", "U+0000"), ("\x1b", "U+001B")):
        with pytest.raises(ValidationError) as exc_info:
            UserProfile.model_validate({**payload, "plan_direction": f"plan {bad} text"})
        msg = str(exc_info.value)
        assert "plan_direction contains control characters" in msg
        assert codepoint in msg


def test_strategist_bundle_exclusion_matches_spec() -> None:
    """The spec's normative Prompt Exposure table
    (docs/specs/user-profile.schema.md) fixes the Strategist bundle exclusion
    set; the adapter constant must match it exactly."""
    from agentic_calendar.llm_nodes.anthropic_adapter import (
        STRATEGIST_BUNDLE_EXCLUDED_PROFILE_FIELDS,
    )

    assert {"resume_text", "experience", "plan_direction", "pathway_selection"} == (
        STRATEGIST_BUNDLE_EXCLUDED_PROFILE_FIELDS
    )
