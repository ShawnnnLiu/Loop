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


# --------------------------------------------------------------------------- #
# add-node + custom CRUD + caps + tombstone deletes (KT-C-c)
# --------------------------------------------------------------------------- #

from agentic_calendar.contracts.career_track import CareerTrack  # noqa: E402
from agentic_calendar.contracts.reason_codes import ReasonCode  # noqa: E402
from agentic_calendar.skill_taxonomy import load_skill_grouping  # noqa: E402


def _addable_skill() -> str:
    """A swe skill with a grouping row that is not on backend-infra's seed map."""
    gmap = knowledge_map_for(BACKEND)
    assert gmap is not None
    on_map = {n.skill_id for n in gmap.nodes if n.skill_id is not None}
    rowed = {e.skill_id for e in load_skill_grouping().entries}
    return next(
        e.skill_id
        for e in load_registry().entries_for_track(CareerTrack.SWE)
        if e.skill_id in rowed and e.skill_id not in on_map
    )


def test_add_node_places_a_new_map_node() -> None:
    service = _service_with_selection()
    before = len(service.knowledge_map_view(USER_ID).nodes)
    skill = _addable_skill()
    view = service.add_knowledge_node(USER_ID, skill_id=skill)
    assert len(view.nodes) == before + 1
    assert node_id_for(skill) in {n.node_id for n in view.nodes}


def test_add_node_already_present_is_typed_rejection() -> None:
    service = _service_with_selection()
    skill = _addable_skill()
    service.add_knowledge_node(USER_ID, skill_id=skill)
    with pytest.raises(CycleError) as exc:
        service.add_knowledge_node(USER_ID, skill_id=skill)
    assert exc.value.reason_code is ReasonCode.KNOWLEDGE_NODE_ALREADY_PRESENT


def test_add_node_off_vocabulary_is_typed_rejection() -> None:
    service = _service_with_selection()
    with pytest.raises(CycleError) as exc:
        service.add_knowledge_node(USER_ID, skill_id="skill.does-not-exist")
    assert exc.value.reason_code is ReasonCode.SKILL_NOT_IN_TRACK_VOCABULARY


def test_add_node_requires_a_selection() -> None:
    service, _env, _clock = make_service(onboard=False, seed_claims=False)
    service.onboard(
        {"user_profile": make_profile([]).model_dump(mode="json"), "timezone": "UTC"}
    )
    with pytest.raises(CycleError, match="no pathway is selected"):
        service.add_knowledge_node(USER_ID, skill_id=_addable_skill())


def test_custom_group_node_create_and_ids_match_pattern() -> None:
    service = _service_with_selection()
    v = service.create_custom_group(USER_ID, name="My cluster")
    gid = next(g.group_id for g in v.groups if g.is_personal)
    assert gid.startswith("kcg-")
    v = service.create_custom_node(USER_ID, name="My node", group_id=gid, description="d")
    node = next(n for n in v.nodes if n.is_personal)
    assert node.node_id.startswith("kcn-")
    assert node.description == "d"


def test_custom_node_in_curated_group_is_allowed() -> None:
    service = _service_with_selection()
    view = service.knowledge_map_view(USER_ID)
    curated_group = next(g.group_id for g in view.groups if not g.is_personal)
    v = service.create_custom_node(USER_ID, name="mine", group_id=curated_group)
    assert any(n.is_personal and n.group_id == curated_group for n in v.nodes)


def test_custom_node_unknown_group_rejected() -> None:
    service = _service_with_selection()
    with pytest.raises(CycleError, match="not on the account"):
        service.create_custom_node(USER_ID, name="x", group_id="kcg-nope")


def test_custom_group_cap_enforced() -> None:
    service = _service_with_selection()
    for i in range(5):
        service.create_custom_group(USER_ID, name=f"g{i}")
    with pytest.raises(CycleError) as exc:
        service.create_custom_group(USER_ID, name="over")
    assert exc.value.reason_code is ReasonCode.CUSTOM_CONTENT_LIMIT_EXCEEDED


def test_custom_node_cap_enforced() -> None:
    service = _service_with_selection()
    gid = next(
        g.group_id
        for g in service.create_custom_group(USER_ID, name="g").groups
        if g.is_personal
    )
    for i in range(20):
        service.create_custom_node(USER_ID, name=f"n{i}", group_id=gid)
    with pytest.raises(CycleError) as exc:
        service.create_custom_node(USER_ID, name="over", group_id=gid)
    assert exc.value.reason_code is ReasonCode.CUSTOM_CONTENT_LIMIT_EXCEEDED


def test_delete_custom_node_removes_it_and_frees_a_slot() -> None:
    service = _service_with_selection()
    gid = next(
        g.group_id
        for g in service.create_custom_group(USER_ID, name="g").groups
        if g.is_personal
    )
    v = service.create_custom_node(USER_ID, name="n", group_id=gid)
    nid = next(n.node_id for n in v.nodes if n.is_personal)
    after = service.delete_custom_node(USER_ID, custom_node_id=nid)
    assert nid not in {n.node_id for n in after.nodes}
    # Freed a slot: 20 more can be created.
    for i in range(20):
        service.create_custom_node(USER_ID, name=f"n{i}", group_id=gid)


def test_delete_custom_group_hides_it() -> None:
    service = _service_with_selection()
    v = service.create_custom_group(USER_ID, name="doomed")
    gid = next(g.group_id for g in v.groups if g.is_personal)
    after = service.delete_custom_group(USER_ID, custom_group_id=gid)
    assert gid not in {g.group_id for g in after.groups}


def test_delete_unknown_custom_content_is_409() -> None:
    service = _service_with_selection()
    with pytest.raises(CycleError, match="not found"):
        service.delete_custom_node(USER_ID, custom_node_id="kcn-nope")
    with pytest.raises(CycleError, match="not found"):
        service.delete_custom_group(USER_ID, custom_group_id="kcg-nope")


def test_delete_note_then_readd_works() -> None:
    service, _env, clock = make_service(onboard=False, seed_claims=False)
    service.onboard(
        {
            "user_profile": make_profile([], selection(pathway_id=BACKEND)).model_dump(
                mode="json"
            ),
            "timezone": "UTC",
        }
    )
    skill = _first_skill(service.knowledge_map_view(USER_ID))
    service.upsert_note(USER_ID, node_id=skill.node_id, text="first")
    clock.advance(minutes=1)
    gone = service.delete_note(USER_ID, node_id=skill.node_id)
    assert next(n for n in gone.nodes if n.node_id == skill.node_id).note is None
    # Re-adding after the delete surfaces the new note (its upsert is later than
    # the tombstone).
    clock.advance(minutes=1)
    again = service.upsert_note(USER_ID, node_id=skill.node_id, text="second")
    assert next(n for n in again.nodes if n.node_id == skill.node_id).note == "second"


# --------------------------------------------------------------------------- #
# skill-proven mark-evidence (KT-C-d)
# --------------------------------------------------------------------------- #


def test_mark_evidence_lifts_a_honed_skill_to_proven() -> None:
    service = _service_with_selection()
    skill = _first_skill(service.knowledge_map_view(USER_ID))
    service.set_mastery(USER_ID, node_id=skill.node_id, target_tier=MasteryTier.HONED)
    view = service.mark_node_evidence(USER_ID, node_id=skill.node_id)
    assert (
        next(n for n in view.nodes if n.node_id == skill.node_id).tier
        is MasteryTier.PROVEN
    )


def test_mark_evidence_before_honed_is_rejected() -> None:
    service = _service_with_selection()
    skill = _first_skill(service.knowledge_map_view(USER_ID))
    with pytest.raises(CycleError, match="honed"):
        service.mark_node_evidence(USER_ID, node_id=skill.node_id)


def test_mark_evidence_on_capstone_rejected() -> None:
    service = _service_with_selection()
    capstone = next(
        n for n in service.knowledge_map_view(USER_ID).nodes if n.kind == "capstone"
    )
    with pytest.raises(CycleError, match="not a skill node"):
        service.mark_node_evidence(USER_ID, node_id=capstone.node_id)


def test_mark_evidence_proven_survives_a_downward_setpoint_on_another_node() -> None:
    # proven is skill-keyed to its own grant; unrelated set-points don't touch it.
    service = _service_with_selection()
    skills = [n for n in service.knowledge_map_view(USER_ID).nodes if n.kind == "skill"]
    a, b = skills[0], skills[1]
    service.set_mastery(USER_ID, node_id=a.node_id, target_tier=MasteryTier.HONED)
    service.mark_node_evidence(USER_ID, node_id=a.node_id)
    service.set_mastery(USER_ID, node_id=b.node_id, target_tier=MasteryTier.DISCOVERED)
    view = service.knowledge_map_view(USER_ID)
    assert next(n for n in view.nodes if n.node_id == a.node_id).tier is MasteryTier.PROVEN
