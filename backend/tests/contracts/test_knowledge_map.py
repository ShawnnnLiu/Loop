"""Tests for the ``KnowledgeMap`` / ``KnowledgeGroup`` / ``KnowledgeNode``
contracts (KT-A)."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from agentic_calendar.contracts.common_types import KnowledgeNodeKind
from agentic_calendar.contracts.knowledge_map import (
    KnowledgeGroup,
    KnowledgeMap,
    KnowledgeNode,
)
from tests._fixture_loader import iter_invalid, iter_valid

CONTRACT = "knowledge_map"


@pytest.mark.parametrize("fixture", list(iter_valid(CONTRACT)), ids=lambda f: f.name)
def test_valid_fixture_parses(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    m = KnowledgeMap.model_validate(payload)
    assert len(m.groups) == len(payload["groups"])
    assert len(m.nodes) == len(payload["nodes"])


@pytest.mark.parametrize("fixture", list(iter_invalid(CONTRACT)), ids=lambda f: f.name)
def test_invalid_fixture_rejected(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    expected = fixture.expected  # type: ignore[attr-defined]
    with pytest.raises(ValidationError) as exc_info:
        KnowledgeMap.model_validate(payload)
    msg = str(exc_info.value)
    for substr in expected["error_substrings"]:
        assert substr in msg, f"expected substring {substr!r} not in:\n{msg}"


def _skill_node(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "node_id": "kn-rag",
        "title": "Retrieval",
        "kind": "skill",
        "skill_id": "skill.rag",
        "group_id": "kg-retrieval",
        "expected_minutes": 360,
    }
    base.update(overrides)
    return base


def test_skill_node_requires_skill_id() -> None:
    with pytest.raises(ValidationError):
        KnowledgeNode.model_validate(_skill_node(skill_id=None))


def test_skill_node_requires_group_id() -> None:
    with pytest.raises(ValidationError):
        KnowledgeNode.model_validate(_skill_node(group_id=None))


def test_skill_node_forbids_evidence_slot_id() -> None:
    with pytest.raises(ValidationError):
        KnowledgeNode.model_validate(_skill_node(evidence_slot_id="x"))


def test_capstone_requires_slot_and_branch() -> None:
    with pytest.raises(ValidationError):
        KnowledgeNode.model_validate(
            {"node_id": "kn-cap", "title": "Cap", "kind": "capstone"}
        )


def test_capstone_forbids_skill_id() -> None:
    with pytest.raises(ValidationError):
        KnowledgeNode.model_validate(
            {
                "node_id": "kn-cap",
                "title": "Cap",
                "kind": "capstone",
                "evidence_slot_id": "s",
                "branch": "s",
                "skill_id": "skill.rag",
            }
        )


def test_node_id_pattern_enforced() -> None:
    with pytest.raises(ValidationError):
        KnowledgeNode.model_validate(_skill_node(node_id="rag"))


def test_group_id_pattern_enforced() -> None:
    with pytest.raises(ValidationError):
        KnowledgeGroup(
            group_id="retrieval",
            title="T",
            branch="b",
            blurb="x",
            member_node_ids=["kn-rag"],
        )


def test_no_edges_field() -> None:
    """The map is groups + nodes only - no edge collection exists."""
    assert "edges" not in KnowledgeMap.model_fields
    assert KnowledgeNodeKind.SKILL.value == "skill"


def test_map_extra_field_forbidden() -> None:
    with pytest.raises(ValidationError):
        KnowledgeMap.model_validate(
            {
                "groups": [
                    {
                        "group_id": "kg-a",
                        "title": "A",
                        "branch": "b",
                        "blurb": "x",
                        "member_node_ids": ["kn-rag"],
                    }
                ],
                "nodes": [_skill_node(group_id="kg-a")],
                "bogus": 1,
            }
        )
