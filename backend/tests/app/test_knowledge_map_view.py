"""Tests for the knowledge-map read + set-point + note-upsert surface (KT-C-b).

The map is a deterministic projection: structure from the pathway registry + the
append-only overlay, tiers from the ``map_state`` fold. Every tier on screen is
reproducible by calling the kernel on stored data (axiom 00 / 11); no LLM
participates. Personal custom content renders as a separate layer and counts
toward nothing.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from agentic_calendar.app.cycle import CycleError, CycleService
from agentic_calendar.contracts.common_types import EvidenceKind, MasteryTier
from agentic_calendar.contracts.knowledge_map_overlay import (
    CustomGroup,
    CustomNode,
    NodeAddition,
)
from agentic_calendar.narrative.generation import node_id_for
from agentic_calendar.skill_taxonomy import load_registry
from agentic_calendar.templates import knowledge_map_for
from tests.app.test_cycle import USER_ID, make_service
from tests.narrative._helpers import item, make_profile, selection

BACKEND = "backend-infrastructure-engineer"
_T0 = datetime(2026, 7, 20, 12, 0, tzinfo=UTC)


def _service_with_selection(
    experience: list[dict[str, Any]] | None = None,
) -> CycleService:
    service, _env, _clock = make_service(onboard=False, seed_claims=False)
    profile = make_profile(experience or [], selection(pathway_id=BACKEND))
    service.onboard(
        {"user_profile": profile.model_dump(mode="json"), "timezone": "UTC"}
    )
    return service


# --------------------------------------------------------------------------- #
# knowledge_map_view — structure + tiers
# --------------------------------------------------------------------------- #


def test_no_selection_yields_empty_map() -> None:
    service, _env, _clock = make_service(onboard=False, seed_claims=False)
    service.onboard(
        {"user_profile": make_profile([]).model_dump(mode="json"), "timezone": "UTC"}
    )
    view = service.knowledge_map_view(USER_ID)
    assert view.has_selection is False
    assert view.pathway_id is None
    assert view.nodes == [] and view.groups == [] and view.branches == []


def test_fresh_selection_is_all_discovered() -> None:
    service = _service_with_selection()
    view = service.knowledge_map_view(USER_ID)

    assert view.has_selection is True
    assert view.pathway_id == BACKEND
    gmap = knowledge_map_for(BACKEND)
    assert gmap is not None
    assert len(view.nodes) == len(gmap.nodes)
    assert {n.tier for n in view.nodes} == {MasteryTier.DISCOVERED}
    # One branch per evidence slot; each carries its capstone.
    from agentic_calendar.contracts.common_types import KnowledgeNodeKind

    capstones = [n for n in gmap.nodes if n.kind is KnowledgeNodeKind.CAPSTONE]
    assert len(view.branches) == len(capstones)
    assert all(b.capstone_node_id.startswith("kn-") for b in view.branches)


def test_filled_slot_lifts_its_capstone_to_proven() -> None:
    # A backend-systems work item fills backend-infra's "service-depth" slot.
    service = _service_with_selection(
        [item("Payments service", EvidenceKind.WORK, ["backend-systems"])]
    )
    view = service.knowledge_map_view(USER_ID)
    service_depth = next(b for b in view.branches if b.slot_id == "service-depth")
    assert service_depth.capstone_tier is MasteryTier.PROVEN
    others = [b for b in view.branches if b.slot_id != "service-depth"]
    assert all(b.capstone_tier is MasteryTier.DISCOVERED for b in others)


def test_node_addition_appears_as_a_map_node() -> None:
    service = _service_with_selection()
    gmap = knowledge_map_for(BACKEND)
    assert gmap is not None
    on_map = {n.skill_id for n in gmap.nodes if n.skill_id is not None}
    from agentic_calendar.contracts.career_track import CareerTrack

    extra = next(
        e.skill_id
        for e in load_registry().entries_for_track(CareerTrack.SWE)
        if e.skill_id not in on_map
    )
    service._env.knowledge_overlay_store.append(
        NodeAddition(user_id=USER_ID, skill_id=extra, created_at=_T0)
    )
    view = service.knowledge_map_view(USER_ID)
    ids = {n.node_id for n in view.nodes}
    assert node_id_for(extra) in ids


# --------------------------------------------------------------------------- #
# set-point + note upsert
# --------------------------------------------------------------------------- #


def _first_skill(view) -> Any:
    return next(n for n in view.nodes if n.kind == "skill")


def test_setpoint_up_and_down_moves_the_tier() -> None:
    service = _service_with_selection()
    skill = _first_skill(service.knowledge_map_view(USER_ID))

    honed = service.set_mastery(USER_ID, node_id=skill.node_id, target_tier=MasteryTier.HONED)
    assert next(n for n in honed.nodes if n.node_id == skill.node_id).tier is MasteryTier.HONED

    # The only path down: a later set-point rebases lower (the feature, 06-…).
    down = service.set_mastery(
        USER_ID, node_id=skill.node_id, target_tier=MasteryTier.DISCOVERED
    )
    assert (
        next(n for n in down.nodes if n.node_id == skill.node_id).tier
        is MasteryTier.DISCOVERED
    )


def test_setpoint_lifts_group_honed_count() -> None:
    service = _service_with_selection()
    view = service.knowledge_map_view(USER_ID)
    skill = _first_skill(view)
    group_before = next(g for g in view.groups if g.group_id == skill.group_id)
    assert group_before.honed_count == 0

    service.set_mastery(USER_ID, node_id=skill.node_id, target_tier=MasteryTier.HONED)
    after = service.knowledge_map_view(USER_ID)
    group_after = next(g for g in after.groups if g.group_id == skill.group_id)
    assert group_after.honed_count == 1


def test_proven_setpoint_rejected() -> None:
    service = _service_with_selection()
    skill = _first_skill(service.knowledge_map_view(USER_ID))
    with pytest.raises(CycleError, match="proven is not settable"):
        service.set_mastery(USER_ID, node_id=skill.node_id, target_tier=MasteryTier.PROVEN)


def test_setpoint_on_unknown_node_rejected() -> None:
    service = _service_with_selection()
    with pytest.raises(CycleError, match="not on the account"):
        service.set_mastery(USER_ID, node_id="kn-does-not-exist", target_tier=MasteryTier.HONED)


def test_note_upsert_newest_wins_and_preserves_created_at() -> None:
    service = _service_with_selection()
    skill = _first_skill(service.knowledge_map_view(USER_ID))

    service.upsert_note(USER_ID, node_id=skill.node_id, text="first")
    view = service.upsert_note(USER_ID, node_id=skill.node_id, text="second")
    assert next(n for n in view.nodes if n.node_id == skill.node_id).note == "second"

    notes = service._env.knowledge_overlay_store.notes_for_user(USER_ID)
    node_notes = [n for n in notes if n.node_id == skill.node_id]
    assert len(node_notes) == 2  # append-only: both retained
    assert node_notes[0].created_at == node_notes[1].created_at  # created_at carried


def test_note_on_unknown_node_rejected() -> None:
    service = _service_with_selection()
    with pytest.raises(CycleError, match="not on the account"):
        service.upsert_note(USER_ID, node_id="kn-nope", text="x")


# --------------------------------------------------------------------------- #
# personal layer (custom content renders, counts toward nothing)
# --------------------------------------------------------------------------- #


def test_custom_group_and_node_render_as_personal_layer() -> None:
    service = _service_with_selection()
    store = service._env.knowledge_overlay_store
    store.append(
        CustomGroup(
            user_id=USER_ID, custom_group_id="kcg-mine", name="My cluster", created_at=_T0
        )
    )
    store.append(
        CustomNode(
            user_id=USER_ID,
            custom_node_id="kcn-thing",
            name="My thing",
            group_id="kcg-mine",
            created_at=_T0,
        )
    )
    view = service.knowledge_map_view(USER_ID)

    custom_group = next(g for g in view.groups if g.group_id == "kcg-mine")
    assert custom_group.is_personal is True
    assert custom_group.honed_count == 0 and custom_group.total_count == 0

    custom_node = next(n for n in view.nodes if n.node_id == "kcn-thing")
    assert custom_node.is_personal is True
    assert custom_node.kind == "custom"
    assert custom_node.tier is MasteryTier.DISCOVERED


def test_custom_node_setpoint_caps_at_honed_and_counts_nothing() -> None:
    service = _service_with_selection()
    store = service._env.knowledge_overlay_store
    store.append(
        CustomNode(
            user_id=USER_ID,
            custom_node_id="kcn-thing",
            name="My thing",
            group_id="kg-anything",  # placement is the user's; irrelevant to counts
            created_at=_T0,
        )
    )
    # A proven set-point on a custom node caps at honed (kernel rule); the API
    # rejects proven outright, so use honed here.
    service.set_mastery(USER_ID, node_id="kcn-thing", target_tier=MasteryTier.HONED)
    view = service.knowledge_map_view(USER_ID)
    node = next(n for n in view.nodes if n.node_id == "kcn-thing")
    assert node.tier is MasteryTier.HONED
    # No pathway branch/group count moved (personal content counts toward nothing).
    assert all(b.honed_count == 0 for b in view.branches)
