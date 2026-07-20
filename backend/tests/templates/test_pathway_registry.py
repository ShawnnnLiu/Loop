"""Registry-level invariants for the pathway registry (NP-B).

The Pydantic contract (``pathway_template.py``) enforces only shape; the
content invariants the spec assigns to "the registry's tests" live here,
mirroring ``tests/templates/test_registry.py``:

- ``pathway_id`` uniqueness within the registry;
- every ``required_themes_any`` member present in its home track's vocabulary;
- every ``branch_skill_ids`` member resolvable against the pinned taxonomy;
- no prestige terms in any text field (reusing the extraction adapter's
  denylist as the single source of truth).
"""

from __future__ import annotations

import pytest

from agentic_calendar.contracts._dedup import casefold_key, find_duplicates
from agentic_calendar.contracts.career_track import CareerTrack
from agentic_calendar.contracts.pathway_template import PathwayTemplate
from agentic_calendar.llm_nodes.anthropic_adapter import _CATEGORY_DENYLIST
from agentic_calendar.skill_taxonomy.registry import load_registry
from agentic_calendar.templates import (
    PATHWAY_REGISTRY_VERSION,
    PATHWAY_SCHEMA_VERSION,
    get_pathway,
    list_pathways,
    pathways_for_track,
    theme_vocabulary,
)

#: Tracks that seed pathways in this registry version.
_LIVE_TRACKS = (CareerTrack.SWE, CareerTrack.MLE, CareerTrack.AI_ENGINEER)

#: Every user-facing/prompt-seed text field of a template, for the denylist scan.
_TEXT_FIELDS = ("display_name", "spine", "audience_note")


def _all_pathways() -> tuple[PathwayTemplate, ...]:
    return list_pathways()


def test_registry_is_non_empty() -> None:
    assert _all_pathways()


def test_pathway_ids_are_unique() -> None:
    ids = [p.pathway_id for p in _all_pathways()]
    assert find_duplicates(ids) == []


def test_get_pathway_round_trips_and_returns_none_for_unknown() -> None:
    for pathway in _all_pathways():
        assert get_pathway(pathway.pathway_id) is pathway
    assert get_pathway("does-not-exist") is None


def test_every_pathway_shares_the_schema_version() -> None:
    for pathway in _all_pathways():
        assert pathway.pathway_schema_version == PATHWAY_SCHEMA_VERSION


def test_registry_version_is_pinned() -> None:
    assert PATHWAY_REGISTRY_VERSION == "pathway-registry-v1"


def test_slot_counts_follow_the_content_guideline() -> None:
    for pathway in _all_pathways():
        assert 4 <= len(pathway.evidence_slots) <= 6, pathway.pathway_id


def test_every_home_track_has_a_theme_vocabulary() -> None:
    for pathway in _all_pathways():
        assert theme_vocabulary(pathway.career_track), pathway.career_track


def test_theme_vocabularies_are_case_insensitively_unique_and_bounded() -> None:
    for track in _LIVE_TRACKS:
        vocab = theme_vocabulary(track)
        assert find_duplicates([casefold_key(t) for t in vocab]) == [], track
        assert len(vocab) <= 30, track


def test_required_themes_are_in_the_home_track_vocabulary() -> None:
    for pathway in _all_pathways():
        allowed = {casefold_key(t) for t in theme_vocabulary(pathway.career_track)}
        for slot in pathway.evidence_slots:
            for theme in slot.required_themes_any:
                assert casefold_key(theme) in allowed, (
                    f"{pathway.pathway_id}/{slot.slot_id}: theme {theme!r} "
                    f"not in the {pathway.career_track} vocabulary"
                )


def test_every_branch_skill_id_resolves_against_the_pinned_taxonomy() -> None:
    registry = load_registry()
    for pathway in _all_pathways():
        for slot in pathway.evidence_slots:
            for skill_id in slot.branch_skill_ids:
                assert registry.by_id(skill_id) is not None, (
                    f"{pathway.pathway_id}/{slot.slot_id}: unknown skill_id {skill_id!r}"
                )


def test_no_prestige_terms_in_any_text_field() -> None:
    for pathway in _all_pathways():
        texts = [getattr(pathway, field) for field in _TEXT_FIELDS]
        for slot in pathway.evidence_slots:
            texts.extend([slot.title, slot.gap_module_hint])
        for text in texts:
            folded = casefold_key(text)
            for term in _CATEGORY_DENYLIST:
                assert casefold_key(term) not in folded, (
                    f"{pathway.pathway_id}: prestige term {term!r} in {text!r}"
                )


@pytest.mark.parametrize(
    ("track", "expected_ids"),
    [
        (
            CareerTrack.SWE,
            (
                "backend-infrastructure-engineer",
                "full-stack-product-engineer",
                "ai-integration-engineer",  # cross-listed from ai_engineer
            ),
        ),
        (CareerTrack.AI_ENGINEER, ("ai-integration-engineer", "llm-systems-engineer")),
        (CareerTrack.MLE, ("applied-ml-specialist",)),
    ],
)
def test_pathways_for_track_includes_cross_listings_in_registry_order(
    track: CareerTrack, expected_ids: tuple[str, ...]
) -> None:
    assert tuple(p.pathway_id for p in pathways_for_track(track)) == expected_ids


def test_cross_listed_pathway_home_track_is_ai_engineer() -> None:
    ai_integration = get_pathway("ai-integration-engineer")
    assert ai_integration is not None
    assert ai_integration.career_track is CareerTrack.AI_ENGINEER
    # It surfaces under swe too, but its themes anchor to ai_engineer.
    assert ai_integration in pathways_for_track(CareerTrack.SWE)
    assert ai_integration in pathways_for_track(CareerTrack.AI_ENGINEER)


def test_a_track_without_seeded_pathways_returns_empty() -> None:
    assert pathways_for_track(CareerTrack.PRODUCT_MANAGER) == ()
    assert theme_vocabulary(CareerTrack.PRODUCT_MANAGER) == ()
