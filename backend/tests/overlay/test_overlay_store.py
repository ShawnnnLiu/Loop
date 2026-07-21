"""Tests for the ``KnowledgeOverlayStore`` implementations (KT-B).

Parametrized over the in-memory and SQLite implementations: both must satisfy
the append-only protocol identically. The restart-survival test at the bottom is
SQLite-only by nature.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from agentic_calendar.common.sqlite import SqliteDatabase
from agentic_calendar.contracts.common_types import (
    MasteryGrantSource,
    MasteryTier,
    PersonalContentKind,
)
from agentic_calendar.contracts.knowledge_map_overlay import (
    CustomGroup,
    CustomNode,
    MasteryGrant,
    MasterySetPoint,
    NodeAddition,
    NodeNote,
    PersonalContentTombstone,
)
from agentic_calendar.overlay.overlay_store import (
    InMemoryKnowledgeOverlayStore,
    KnowledgeOverlayStore,
)
from agentic_calendar.overlay.sqlite_overlay_store import SqliteKnowledgeOverlayStore

_NOW = datetime(2026, 7, 20, 12, 0, tzinfo=UTC)


@pytest.fixture(params=["in_memory", "sqlite"])
def store(request: pytest.FixtureRequest, tmp_path: Path) -> KnowledgeOverlayStore:
    if request.param == "sqlite":
        return SqliteKnowledgeOverlayStore(SqliteDatabase(tmp_path / "overlay.db"))
    return InMemoryKnowledgeOverlayStore()


def _grant(user_id: str = "u1", node_id: str = "kn-rag", minutes: int = 60) -> MasteryGrant:
    return MasteryGrant(
        user_id=user_id,
        node_id=node_id,
        credit_minutes=minutes,
        source=MasteryGrantSource.ONBOARDING,
        created_at=_NOW,
    )


def _setpoint(
    user_id: str = "u1", node_id: str = "kn-rag", tier: MasteryTier = MasteryTier.HONED
) -> MasterySetPoint:
    return MasterySetPoint(
        user_id=user_id, node_id=node_id, target_tier=tier, created_at=_NOW
    )


def _addition(user_id: str = "u1", skill_id: str = "skill.rag") -> NodeAddition:
    return NodeAddition(user_id=user_id, skill_id=skill_id, created_at=_NOW)


def _group(user_id: str = "u1", gid: str = "kcg-mine") -> CustomGroup:
    return CustomGroup(
        user_id=user_id, custom_group_id=gid, name="My group", created_at=_NOW
    )


def _node(user_id: str = "u1", nid: str = "kcn-mine") -> CustomNode:
    return CustomNode(
        user_id=user_id,
        custom_node_id=nid,
        name="My node",
        group_id="kcg-mine",
        created_at=_NOW,
    )


def _note(user_id: str = "u1", node_id: str = "kn-rag", text: str = "note") -> NodeNote:
    return NodeNote(
        user_id=user_id, node_id=node_id, text=text, created_at=_NOW, updated_at=_NOW
    )


def _tombstone(
    user_id: str = "u1",
    kind: PersonalContentKind = PersonalContentKind.CUSTOM_NODE,
    target_id: str = "kcn-mine",
) -> PersonalContentTombstone:
    return PersonalContentTombstone(
        user_id=user_id, target_kind=kind, target_id=target_id, created_at=_NOW
    )


def test_each_record_type_round_trips_under_its_reader(
    store: KnowledgeOverlayStore,
) -> None:
    store.append(_addition())
    store.append(_group())
    store.append(_node())
    store.append(_note())
    store.append(_grant())
    store.append(_setpoint())
    store.append(_tombstone())

    assert store.node_additions_for_user("u1") == [_addition()]
    assert store.custom_groups_for_user("u1") == [_group()]
    assert store.custom_nodes_for_user("u1") == [_node()]
    assert store.notes_for_user("u1") == [_note()]
    assert store.mastery_grants_for_user("u1") == [_grant()]
    assert store.setpoints_for_user("u1") == [_setpoint()]
    assert store.tombstones_for_user("u1") == [_tombstone()]


def test_reads_preserve_insertion_order(store: KnowledgeOverlayStore) -> None:
    store.append(_grant(node_id="kn-a"))
    store.append(_grant(node_id="kn-b"))
    store.append(_grant(node_id="kn-c"))
    assert [g.node_id for g in store.mastery_grants_for_user("u1")] == [
        "kn-a",
        "kn-b",
        "kn-c",
    ]


def test_append_only_keeps_duplicates_never_dedups(
    store: KnowledgeOverlayStore,
) -> None:
    # The store is an immutable log; per-account id uniqueness is a KT-C concern.
    store.append(_setpoint(tier=MasteryTier.TRAINING))
    store.append(_setpoint(tier=MasteryTier.HONED))
    tiers = [s.target_tier for s in store.setpoints_for_user("u1")]
    assert tiers == [MasteryTier.TRAINING, MasteryTier.HONED]


def test_reads_are_scoped_to_the_user(store: KnowledgeOverlayStore) -> None:
    store.append(_grant(user_id="u1", node_id="kn-a"))
    store.append(_grant(user_id="u2", node_id="kn-b"))
    assert [g.node_id for g in store.mastery_grants_for_user("u1")] == ["kn-a"]
    assert [g.node_id for g in store.mastery_grants_for_user("u2")] == ["kn-b"]


def test_delete_for_user_removes_all_records_and_returns_the_count(
    store: KnowledgeOverlayStore,
) -> None:
    store.append(_grant(user_id="u1"))
    store.append(_note(user_id="u1"))
    store.append(_grant(user_id="u2"))

    assert store.delete_for_user("u1") == 2
    assert store.mastery_grants_for_user("u1") == []
    assert store.notes_for_user("u1") == []
    # u2 is untouched.
    assert store.mastery_grants_for_user("u2") == [_grant(user_id="u2")]


def test_missing_user_reads_empty(store: KnowledgeOverlayStore) -> None:
    assert store.node_additions_for_user("nobody") == []
    assert store.delete_for_user("nobody") == 0


def test_sqlite_survives_restart(tmp_path: Path) -> None:
    path = tmp_path / "overlay.db"
    first = SqliteKnowledgeOverlayStore(SqliteDatabase(path))
    first.append(_grant())
    first.append(_group())

    # Reopen against the same file - a fresh process would see this.
    second = SqliteKnowledgeOverlayStore(SqliteDatabase(path))
    assert second.mastery_grants_for_user("u1") == [_grant()]
    assert second.custom_groups_for_user("u1") == [_group()]
