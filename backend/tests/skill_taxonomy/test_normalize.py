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
        ("Data Scientist", CareerTrack.DATA_SCIENTIST),
        ("Senior Data Scientist", CareerTrack.DATA_SCIENTIST),
        ("Product Data Scientist", CareerTrack.DATA_SCIENTIST),
        ("Decision Scientist", CareerTrack.DATA_SCIENTIST),
        ("Data Science Manager", CareerTrack.DATA_SCIENTIST),
        ("Data Engineer", CareerTrack.DATA_ENGINEER),
        ("Senior Data Engineer", CareerTrack.DATA_ENGINEER),
        ("ETL Developer", CareerTrack.DATA_ENGINEER),
        ("Big Data Engineer", CareerTrack.DATA_ENGINEER),
        ("Data Platform Engineer", CareerTrack.DATA_ENGINEER),
        ("Data Analyst", CareerTrack.DATA_ANALYST),
        ("Senior Data Analyst", CareerTrack.DATA_ANALYST),
        ("Business Intelligence Analyst", CareerTrack.DATA_ANALYST),
        ("BI Analyst", CareerTrack.DATA_ANALYST),
        ("Reporting Analyst", CareerTrack.DATA_ANALYST),
        ("Product Analyst", CareerTrack.DATA_ANALYST),
        ("Marketing Analytics Manager", CareerTrack.DATA_ANALYST),
        ("Chef", None),
        ("Product Manager", None),
        # "business analyst" is ruled to the future business_analyst track
        # (career-track-expansion 02-shared-entries.md); until it lands the
        # role falls to the union fallback, NOT to data_analyst.
        ("Business Analyst", None),
        # "quantitative analyst" is deliberately unresolved: quant_dev is an
        # enum track with no markers yet, and approximating quant-finance
        # roles to data_scientist (the career profile's draft) was ruled
        # out. A quant_dev marker increment re-homes this.
        ("Quantitative Analyst", None),
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


def test_data_analyst_precedence_beats_swe() -> None:
    """"analytics" precedes the SWE tuple, so an analytics title naming an
    engineering-flavored word still resolves to data_analyst."""
    assert resolve_track("Data Analytics Developer") is CareerTrack.DATA_ANALYST


def test_data_scientist_precedence_beats_data_analyst() -> None:
    """The DATA_SCIENTIST tuple precedes DATA_ANALYST, so a mixed title
    naming both "data science" and an analytics word takes the more
    specific track."""
    assert resolve_track("Data Science Analyst") is CareerTrack.DATA_SCIENTIST


def test_ml_scientist_precedence_stays_with_mle() -> None:
    """MLE precedes DATA_SCIENTIST (career profile ruling: mle markers stay
    first), so ML-scientist titles do not drift to the new tuple."""
    assert resolve_track("Machine Learning Scientist") is CareerTrack.MLE
    assert resolve_track("ML Scientist") is CareerTrack.MLE


def test_analytics_engineer_re_homed_to_data_engineer() -> None:
    """The interim ruling (bare "analytics" claimed "analytics engineer"
    for data_analyst until the data_engineer track landed) is retired: the
    DATA_ENGINEER tuple precedes DATA_ANALYST, so the dbt-centric middle
    role now resolves to data_engineer per the career profile."""
    assert resolve_track("Analytics Engineer") is CareerTrack.DATA_ENGINEER
    # Other analytics titles stay with data_analyst.
    assert resolve_track("Marketing Analytics Manager") is CareerTrack.DATA_ANALYST


def test_data_platform_precedence_beats_swe() -> None:
    """DATA_ENGINEER precedes SWE, so a platform-flavored data title does
    not fall through to the "platform engineer" software marker."""
    assert resolve_track("Data Platform Engineer") is CareerTrack.DATA_ENGINEER
