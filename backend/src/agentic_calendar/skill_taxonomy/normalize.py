"""Pure normalization: surface strings → taxonomy entries; role → track.

Canonical spec: ``docs/specs/skill-taxonomy.schema.md`` (Normalization
Semantics). Normalization is lowercase, whitespace-collapse, and a light
punctuation strip; **no fuzzy or similarity matching in v1** — similarity
thresholds are guesswork until calibrated, and the restraint is the
behavior. A surface that matches nothing resolves to ``None`` (the caller
flags it unmatched; it is never silently promoted to a canonical skill).
"""

from __future__ import annotations

import re

from agentic_calendar.contracts.career_track import CareerTrack
from agentic_calendar.contracts.skill_taxonomy import SkillEntry

from .registry import SkillTaxonomyRegistry

# Sentence punctuation trimmed from surface edges. Deliberately narrow so the
# strip is idempotent on every stored alias: no ``+``/``#``/``&``/``/``/``-``
# (load-bearing inside ``c++``, ``c#``, ``w&b``, ``ci/cd``, ``big-o``) and no
# LEADING dot (``.net``); a trailing dot is sentence punctuation and safe —
# no alias ends with one (the seed property test would catch one that did).
_LEADING_STRIP = "\"'`,;:!?()[]{}"
_TRAILING_STRIP = _LEADING_STRIP + "."


def normalize_surface(surface: str) -> str:
    """Lowercase, collapse whitespace, strip surrounding sentence punctuation.

    Total and deterministic; idempotent on every stored alias (aliases are
    already lowercase-normalized, contract-enforced).
    """
    text = " ".join(surface.lower().split())
    while True:
        stripped = " ".join(
            text.lstrip(_LEADING_STRIP).rstrip(_TRAILING_STRIP).split()
        )
        if stripped == text:
            return text
        text = stripped


def resolve(surface: str, registry: SkillTaxonomyRegistry) -> SkillEntry | None:
    """Map one free-text surface onto its taxonomy entry, or ``None``.

    Exact alias lookup after :func:`normalize_surface` — total,
    deterministic, and collision-free by construction (global alias
    uniqueness is contract-enforced).
    """
    return registry.by_alias(normalize_surface(surface))


# Role→track markers, matched with non-alphanumeric boundaries against the
# normalized role string. Precedence is fixed and deliberate: the ML and AI
# marker sets are more specific than the SWE set ("ml engineer" must not fall
# through to swe via "engineer"-adjacent words), so they are checked first.
_TRACK_MARKERS: tuple[tuple[CareerTrack, tuple[str, ...]], ...] = (
    (
        CareerTrack.MLE,
        ("machine learning", "ml engineer", "ml scientist", "mle", "deep learning"),
    ),
    (
        CareerTrack.AI_ENGINEER,
        ("ai engineer", "ai engineering", "llm", "genai", "generative ai", "applied ai"),
    ),
    (
        # After MLE so "ml scientist"/"machine learning scientist" keep
        # resolving there; before DATA_ANALYST so mixed titles like "data
        # science analyst" take the more specific track. "quantitative
        # analyst" is deliberately absent — quant_dev is an enum track with
        # no markers yet, so the title stays on the union fallback rather
        # than being approximated to data_scientist (ruling against the
        # career profile's draft, 2026-07-19).
        CareerTrack.DATA_SCIENTIST,
        ("data scientist", "data science", "decision scientist"),
    ),
    (
        # After DATA_SCIENTIST (mixed "data science …" titles keep the more
        # specific track) and before DATA_ANALYST, whose bare "analytics"
        # marker would otherwise claim "analytics engineer" — the dbt-centric
        # middle role is ruled to data_engineer (career profile judgment
        # call: warehouse/dbt vocabulary stays in scope). Also precedes SWE
        # so "data platform engineer" does not fall through to
        # "platform engineer".
        CareerTrack.DATA_ENGINEER,
        (
            "data engineer",
            "data engineering",
            "analytics engineer",
            "etl developer",
            "data platform",
            "big data engineer",
        ),
    ),
    (
        # Precedes SWE so BI/analytics titles never fall through to
        # engineering markers. "business analyst" is deliberately absent —
        # it is ruled to the future business_analyst track. Bare
        # "analytics" claims the remaining analytics titles now that
        # "analytics engineer" is re-homed by the preceding data_engineer
        # tuple.
        CareerTrack.DATA_ANALYST,
        (
            "data analyst",
            "data analytics",
            "business intelligence",
            "bi analyst",
            "analytics",
            "reporting analyst",
            "product analyst",
        ),
    ),
    (
        CareerTrack.SWE,
        (
            "software",
            "swe",
            "backend",
            "back-end",
            "back end",
            "frontend",
            "front-end",
            "front end",
            "full stack",
            "full-stack",
            "fullstack",
            "web developer",
            "developer",
            "platform engineer",
            "infrastructure",
            "site reliability",
            "sre",
            "devops",
        ),
    ),
)


def _contains_marker(text: str, marker: str) -> bool:
    return (
        re.search(
            rf"(?<![a-z0-9]){re.escape(marker)}(?![a-z0-9])",
            text,
        )
        is not None
    )


def resolve_track(target_role: str | None) -> CareerTrack | None:
    """Deterministic role→track mapping; ``None`` when unresolvable.

    No LLM, no scoring: a small marker table with fixed precedence. An
    unresolvable role means the caller uses the union of all tracks as the
    weak-spot choice set.
    """
    if target_role is None:
        return None
    normalized = normalize_surface(target_role)
    for track, markers in _TRACK_MARKERS:
        if any(_contains_marker(normalized, marker) for marker in markers):
            return track
    return None
