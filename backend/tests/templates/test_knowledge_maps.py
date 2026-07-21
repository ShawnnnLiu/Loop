"""Committed knowledge-map artifact: drift guard + loader (KT-B).

The generator is deterministic and its output is committed
(``pathways/knowledge_maps.json``); this test is the in-suite twin of
``make maps-check`` so a stale artifact fails the ordinary run, not only CI.
"""

from __future__ import annotations

from agentic_calendar.templates import (
    DEFAULT_KNOWLEDGE_MAPS_PATH,
    knowledge_map_for,
    list_pathways,
    load_knowledge_maps,
    pathway_with_map,
)
from agentic_calendar.tools.generate_knowledge_maps import render_artifact


def test_committed_artifact_matches_regeneration() -> None:
    committed = DEFAULT_KNOWLEDGE_MAPS_PATH.read_text(encoding="utf-8")
    assert committed == render_artifact(), (
        "pathways/knowledge_maps.json is stale - run `make maps` and commit"
    )


def test_loader_returns_a_map_for_every_registered_pathway() -> None:
    maps = load_knowledge_maps()
    assert set(maps) == {p.pathway_id for p in list_pathways()}


def test_pathway_with_map_attaches_a_validated_map() -> None:
    for pathway in list_pathways():
        composed = pathway_with_map(pathway.pathway_id)
        assert composed is not None
        assert composed.knowledge_map is not None
        assert composed.knowledge_map == knowledge_map_for(pathway.pathway_id)


def test_unknown_pathway_has_no_map() -> None:
    assert knowledge_map_for("does-not-exist") is None
    assert pathway_with_map("does-not-exist") is None
