"""Property tests for the pure normalizer, resolver, and role→track mapping.

The properties run over EVERY alias in the checked-in seed vocabulary, so a
future alias that breaks normalization idempotence (e.g. one ending in a
character the strip set trims) fails here and forces a deliberate decision.
"""

from __future__ import annotations

import pytest

from agentic_calendar.contracts.career_track import CareerTrack
from agentic_calendar.skill_taxonomy import (
    load_registry,
    normalize_surface,
    resolve,
    resolve_track,
)

_REGISTRY = load_registry()
_ALIAS_TO_ID = {
    alias: entry.skill_id for entry in _REGISTRY.entries for alias in entry.aliases
}


@pytest.mark.parametrize("alias", sorted(_ALIAS_TO_ID))
def test_normalize_is_idempotent_on_every_stored_alias(alias: str) -> None:
    assert normalize_surface(alias) == alias


@pytest.mark.parametrize("alias", sorted(_ALIAS_TO_ID))
def test_every_alias_resolves_through_casing_and_padding_variants(alias: str) -> None:
    expected = _ALIAS_TO_ID[alias]
    for variant in (
        alias,
        alias.upper(),
        alias.title(),
        f"  {alias}  ",
        f"({alias}),",
    ):
        entry = resolve(variant, _REGISTRY)
        assert entry is not None, f"variant {variant!r} failed to resolve"
        assert entry.skill_id == expected


def test_normalize_collapses_internal_whitespace() -> None:
    assert normalize_surface("System   Design") == "system design"
    assert resolve("system\tdesign", _REGISTRY) is not None


def test_normalize_strips_nested_sentence_punctuation() -> None:
    assert normalize_surface("( 'Python' )") == "python"


def test_normalize_preserves_load_bearing_punctuation() -> None:
    # ``+``/``#``/``&``/``/``/``-`` and a leading dot are alias content, not
    # sentence punctuation — stripping them would break these resolutions.
    assert normalize_surface("C++") == "c++"
    assert normalize_surface("C#") == "c#"
    assert normalize_surface(".NET") == ".net"
    assert normalize_surface("CI/CD") == "ci/cd"
    assert normalize_surface("W&B") == "w&b"
    assert normalize_surface("Big-O") == "big-o"


@pytest.mark.parametrize(
    "near_miss",
    [
        "pythonn",
        "java script",
        "sci kit learn",
        "postgress",
        "kubernets",
    ],
)
def test_near_misses_do_not_resolve(near_miss: str) -> None:
    """The restraint test: no fuzzy/similarity matching in v1."""
    assert resolve(near_miss, _REGISTRY) is None


@pytest.mark.parametrize(
    "garbage",
    ["", "   ", "??!!", "완전히 다른 문자열", "a" * 500, "\n\t"],
)
def test_resolve_is_total_on_arbitrary_strings(garbage: str) -> None:
    assert resolve(garbage, _REGISTRY) is None


@pytest.mark.parametrize(
    ("target_role", "expected"),
    [
        ("Backend SWE", CareerTrack.SWE),
        ("backend engineer", CareerTrack.SWE),
        ("Frontend Developer", CareerTrack.SWE),
        ("Software Engineer", CareerTrack.SWE),
        ("Site Reliability Engineer", CareerTrack.SWE),
        ("ML Engineer", CareerTrack.MLE),
        ("Machine Learning Scientist", CareerTrack.MLE),
        ("Deep Learning Researcher", CareerTrack.MLE),
        ("AI Engineer", CareerTrack.AI_ENGINEER),
        ("LLM engineer", CareerTrack.AI_ENGINEER),
        ("GenAI application developer", CareerTrack.AI_ENGINEER),
        ("Chef", None),
        ("Product Manager", None),
        (None, None),
    ],
)
def test_resolve_track_deterministic_marker_map(
    target_role: str | None, expected: CareerTrack | None
) -> None:
    assert resolve_track(target_role) is expected


def test_resolve_track_precedence_ml_beats_swe() -> None:
    """A role naming both ML and software markers maps to the more specific
    track — the fixed precedence, not an accident of ordering."""
    assert resolve_track("Machine Learning Software Engineer") is CareerTrack.MLE


def test_genai_developer_precedence_ai_beats_swe() -> None:
    assert resolve_track("GenAI developer") is CareerTrack.AI_ENGINEER
