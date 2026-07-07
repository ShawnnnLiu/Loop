"""Tests for the fixture ResumeIntake node (keyless-dev twin)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from agentic_calendar.contracts.resume_extraction import ResumeExtraction
from agentic_calendar.contracts.resume_intake_input import (
    DraftProfileContext,
    ResumeIntakeInput,
)
from agentic_calendar.llm_nodes.resume_intake import FixtureResumeIntake

#: Plain alias→display data, the shape the composition root extracts from the
#: taxonomy registry (this test deliberately does NOT import the kernel —
#: the twin's contract is that the vocabulary arrives as data).
_ALIASES: dict[str, str] = {
    "python": "Python",
    "python3": "Python",
    "go": "Go",
    "golang": "Go",
    "c": "C",
    "c++": "C++",
    "kubernetes": "Kubernetes",
    "k8s": "Kubernetes",
    "system design": "System design",
}

_RESUME = (
    "Senior Backend Engineer at Acme Corp (2019-2024)\n"
    "Led the billing platform team; Python and Go services on Kubernetes.\n"
    "Software Engineer at Initech\n"
    "Wrote C++ image pipelines and Python3 tooling."
)


def _node() -> FixtureResumeIntake:
    return FixtureResumeIntake(taxonomy_aliases=_ALIASES)


def _intake(
    *,
    resume_text: str = _RESUME,
    target_role: str | None = "Backend SWE",
    allowed_weak_spots: list[str] | None = None,
) -> ResumeIntakeInput:
    return ResumeIntakeInput(
        user_id="user_t",
        resume_text=resume_text,
        draft_context=DraftProfileContext(target_role=target_role),
        allowed_weak_spots=allowed_weak_spots or [],
    )


def test_constructor_rejects_empty_alias_mapping() -> None:
    with pytest.raises(ValueError, match="non-empty alias mapping"):
        FixtureResumeIntake(taxonomy_aliases={})


def test_same_input_yields_identical_output() -> None:
    node = _node()
    first = node.run(run_id="intake-t", intake=_intake())
    second = node.run(run_id="intake-t", intake=_intake())
    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    assert isinstance(first, ResumeExtraction)


def test_skills_are_grounded_resume_spans() -> None:
    extraction = _node().run(run_id="intake-t", intake=_intake())
    lowered = _RESUME.lower()
    assert extraction.skills, "expected the alias scan to find skills"
    for surface in extraction.skills:
        assert surface.lower() in lowered


def test_skills_use_word_boundaries_not_substrings() -> None:
    resume = (
        "Going forward I study category theory and lambda calculus at night, "
        "and write documentation for the platform team."
    )
    extraction = _node().run(run_id="intake-t", intake=_intake(resume_text=resume))
    # "Going" must not match alias "go"; "category" must not match alias "c".
    assert extraction.skills == []


def test_c_alias_does_not_match_inside_cpp() -> None:
    resume = "Software Engineer at Initech\nWrote C++ services for ten years there."
    extraction = _node().run(run_id="intake-t", intake=_intake(resume_text=resume))
    assert "C++" in extraction.skills
    assert "C" not in extraction.skills


def test_one_skill_per_canonical_entry() -> None:
    # _RESUME mentions both "Python" and "Python3"; one Python skill results.
    extraction = _node().run(run_id="intake-t", intake=_intake())
    python_surfaces = [s for s in extraction.skills if s.lower().startswith("python")]
    assert len(python_surfaces) == 1


def test_skills_ordered_by_resume_position() -> None:
    extraction = _node().run(run_id="intake-t", intake=_intake())
    positions = [_RESUME.lower().index(s.lower()) for s in extraction.skills]
    assert positions == sorted(positions)


def test_experience_lines_parse_title_and_trimmed_org() -> None:
    extraction = _node().run(run_id="intake-t", intake=_intake())
    pairs = [(item.title, item.organization) for item in extraction.experience]
    assert ("Senior Backend Engineer", "Acme Corp") in pairs  # "(2019-2024)" trimmed
    assert ("Software Engineer", "Initech") in pairs


def test_experience_caps_at_three_and_dedupes() -> None:
    resume = "\n".join(
        [
            "Engineer at Acme",
            "Engineer at Acme",  # duplicate (title, org) — dropped
            "Engineer at Beta LLC",
            "Engineer at Gamma Inc",
            "Engineer at Delta Co",  # fourth unique — beyond the cap
        ]
    ) + "\nPadding so the résumé clears the contract's minimum length."
    extraction = _node().run(run_id="intake-t", intake=_intake(resume_text=resume))
    orgs = [item.organization for item in extraction.experience]
    assert orgs == ["Acme", "Beta LLC", "Gamma Inc"]


def test_no_experience_pattern_yields_empty_list() -> None:
    resume = (
        "A prose-only summary of skills and interests without any employment "
        "lines in the recognized separator shape."
    )
    extraction = _node().run(run_id="intake-t", intake=_intake(resume_text=resume))
    assert extraction.experience == []


def test_canned_lists_keyed_by_target_role() -> None:
    extraction = _node().run(run_id="intake-t", intake=_intake(target_role="Backend SWE"))
    assert extraction.known_strengths == ["backend services", "API design"]
    assert extraction.target_company_categories == ["infra startups", "big tech"]


def test_unknown_role_falls_back_to_generic_canned_set() -> None:
    extraction = _node().run(run_id="intake-t", intake=_intake(target_role="Chef"))
    assert extraction.known_strengths == ["shipped real projects"]


def test_missing_role_falls_back_to_generic_canned_set() -> None:
    extraction = _node().run(run_id="intake-t", intake=_intake(target_role=None))
    assert extraction.known_strengths == ["shipped real projects"]


def test_weak_spots_honor_the_allowed_vocabulary() -> None:
    allowed = ["System design", "Dynamic programming", "SQL"]
    extraction = _node().run(
        run_id="intake-t", intake=_intake(allowed_weak_spots=allowed)
    )
    assert extraction.inferred_weak_spots
    assert set(extraction.inferred_weak_spots) <= set(allowed)


def test_weak_spots_fall_back_to_first_allowed_entries_when_canned_miss() -> None:
    allowed = ["Graph algorithms", "Concurrency"]  # no canned overlap
    extraction = _node().run(
        run_id="intake-t", intake=_intake(allowed_weak_spots=allowed)
    )
    assert extraction.inferred_weak_spots == ["Graph algorithms", "Concurrency"]


def test_empty_allowed_vocabulary_passes_canned_through() -> None:
    extraction = _node().run(run_id="intake-t", intake=_intake(allowed_weak_spots=[]))
    assert extraction.inferred_weak_spots == ["System design", "Dynamic programming"]


def test_boundary_revalidation_rejects_contract_violating_input() -> None:
    """An input built around the contract (``model_construct``) is rejected
    at the node boundary, not silently extracted from."""
    bad = ResumeIntakeInput.model_construct(
        user_id="user_t",
        resume_text="too short",
        draft_context=DraftProfileContext(),
        allowed_weak_spots=[],
    )
    with pytest.raises(ValidationError):
        _node().run(run_id="intake-t", intake=bad)
