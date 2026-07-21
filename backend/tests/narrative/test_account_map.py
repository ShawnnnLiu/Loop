"""Tests for the pathway-content node vocabulary (KT-C).

``pathway_node_vocabulary`` is the pure projection both the Strategist bundle and
the deterministic gate build on, so it must be byte-stable: generated skill nodes
in committed order, then taxonomy-anchored additions by ``node_id``, capstones
excluded, personal content never present.
"""

from __future__ import annotations

from datetime import UTC, datetime

from agentic_calendar.contracts.common_types import KnowledgeNodeKind
from agentic_calendar.contracts.knowledge_map import (
    KnowledgeGroup,
    KnowledgeMap,
    KnowledgeNode,
)
from agentic_calendar.contracts.knowledge_map_overlay import NodeAddition
from agentic_calendar.narrative import pathway_node_vocabulary

_T0 = datetime(2026, 7, 20, 12, 0, tzinfo=UTC)


def _map() -> KnowledgeMap:
    return KnowledgeMap(
        groups=[
            KnowledgeGroup(
                group_id="kg-core",
                title="Core",
                branch="core",
                blurb="b",
                member_node_ids=["kn-rag", "kn-embeddings"],
            )
        ],
        nodes=[
            KnowledgeNode(
                node_id="kn-rag",
                title="Retrieval fundamentals",
                kind=KnowledgeNodeKind.SKILL,
                skill_id="skill.rag",
                group_id="kg-core",
                expected_minutes=360,
            ),
            KnowledgeNode(
                node_id="kn-embeddings",
                title="Embeddings",
                kind=KnowledgeNodeKind.SKILL,
                skill_id="skill.embeddings",
                group_id="kg-core",
                expected_minutes=180,
            ),
            KnowledgeNode(
                node_id="kn-s1-capstone",
                title="Capstone",
                kind=KnowledgeNodeKind.CAPSTONE,
                evidence_slot_id="s1",
                branch="s1",
            ),
        ],
    )


def _addition(skill_id: str) -> NodeAddition:
    return NodeAddition(user_id="u1", skill_id=skill_id, created_at=_T0)


def test_generated_skill_nodes_only_in_committed_order() -> None:
    # Capstone excluded (not a training target); order matches the map.
    assert pathway_node_vocabulary(_map(), display_names={}) == [
        ("kn-rag", "Retrieval fundamentals"),
        ("kn-embeddings", "Embeddings"),
    ]


def test_additions_appended_sorted_by_node_id() -> None:
    vocab = pathway_node_vocabulary(
        _map(),
        additions=[_addition("skill.testing"), _addition("skill.git")],
        display_names={"skill.testing": "Testing", "skill.git": "Git"},
    )
    # Generated first (map order), then additions sorted by node_id (git < testing).
    assert vocab == [
        ("kn-rag", "Retrieval fundamentals"),
        ("kn-embeddings", "Embeddings"),
        ("kn-git", "Git"),
        ("kn-testing", "Testing"),
    ]


def test_addition_already_generated_is_not_duplicated() -> None:
    vocab = pathway_node_vocabulary(
        _map(),
        additions=[_addition("skill.rag")],
        display_names={"skill.rag": "Retrieval fundamentals"},
    )
    assert [node_id for node_id, _ in vocab] == ["kn-rag", "kn-embeddings"]


def test_addition_without_display_name_is_skipped_defensively() -> None:
    vocab = pathway_node_vocabulary(
        _map(), additions=[_addition("skill.unknown")], display_names={}
    )
    assert [node_id for node_id, _ in vocab] == ["kn-rag", "kn-embeddings"]
