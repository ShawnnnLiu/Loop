"""Tests for the narrative pathways read projection + constraints (NP-D-b).

``pathways_view`` and ``_pathway_constraints`` compute everything through the
``narrative/`` kernel over the *stored* profile - no LLM participates - so these
tests pin coverage counts, card ordering, the selected flag, version-mismatch
surfacing, and the unfilled-slot projection the Strategist is handed.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from agentic_calendar.app.cycle import CycleService
from agentic_calendar.app.state import OnboardingRecord
from agentic_calendar.contracts.career_track import CareerTrack
from agentic_calendar.contracts.common_types import EvidenceKind, KnowledgeNodeKind
from agentic_calendar.contracts.knowledge_map_overlay import NodeAddition
from agentic_calendar.narrative.generation import node_id_for
from agentic_calendar.skill_taxonomy import load_registry
from agentic_calendar.templates import knowledge_map_for
from tests.app.test_cycle import USER_ID, make_service
from tests.narrative._helpers import item, make_profile, selection

BACKEND = "backend-infrastructure-engineer"


def _onboard(
    service: CycleService,
    experience: list[dict[str, Any]],
    pathway_selection: dict[str, Any] | None = None,
) -> None:
    profile = make_profile(experience, pathway_selection)
    service.onboard(
        {"user_profile": profile.model_dump(mode="json"), "timezone": "UTC"}
    )


def _service() -> CycleService:
    service, _env, _clock = make_service(onboard=False, seed_claims=False)
    return service


# --------------------------------------------------------------------------- #
# pathways_view
# --------------------------------------------------------------------------- #


def test_coverage_and_ordering_are_kernel_computed() -> None:
    service = _service()
    # A backend-systems work item fills backend-infra's "service-depth" slot.
    _onboard(service, [item("Payments service", EvidenceKind.WORK, ["backend-systems"])])
    result = service.pathways_view(USER_ID, track="swe")

    assert result.track is not None and result.track.value == "swe"
    assert result.registry_version == "pathway-registry-v1"
    ids = [c.pathway_id for c in result.cards]
    assert BACKEND in ids

    backend = next(c for c in result.cards if c.pathway_id == BACKEND)
    depth = next(s for s in backend.slots if s.slot_id == "service-depth")
    assert depth.state.value == "filled"
    assert depth.matched_item_indices == [0]
    assert backend.filled_slots >= 1
    assert backend.total_slots == len(backend.slots)

    # Cards are ordered by filled_slots descending (ties keep registry order).
    counts = [c.filled_slots for c in result.cards]
    assert counts == sorted(counts, reverse=True)


def test_selected_card_flagged_no_mismatch_when_pinned_current() -> None:
    service = _service()
    _onboard(
        service,
        [item("Payments service", EvidenceKind.WORK, ["backend-systems"])],
        pathway_selection=selection(pathway_id=BACKEND),
    )
    result = service.pathways_view(USER_ID, track="swe")

    assert result.selected_pathway_id == BACKEND
    assert result.version_mismatch is False
    assert [c.pathway_id for c in result.cards if c.selected] == [BACKEND]


def test_stale_version_pin_surfaces_mismatch_without_remap() -> None:
    # A stale pin cannot be created through onboard (it rejects one, NP-D-c);
    # it only arises when a *later* registry bump orphans an already-stored
    # selection. Simulate that by writing the record directly, then assert
    # pathways_view surfaces the mismatch rather than silently re-mapping.
    service, env, clock = make_service(onboard=False, seed_claims=False)
    stale = selection(pathway_id=BACKEND)
    stale["pathway_registry_version"] = "pathway-registry-v0"
    profile = make_profile([], stale)
    now = clock.now()
    env.state.save_onboarding(
        OnboardingRecord.model_validate(
            {
                "user_id": USER_ID,
                "user_profile": profile.model_dump(mode="json"),
                "timezone": "UTC",
                "created_at": now,
                "updated_at": now,
            }
        )
    )
    result = service.pathways_view(USER_ID, track="swe")

    assert result.version_mismatch is True
    # The user's pick still highlights - the UI prompts a re-confirm.
    assert result.selected_pathway_id == BACKEND


def test_track_defaults_to_profile_role() -> None:
    service = _service()
    _onboard(service, [])  # fixture profile target_role "Backend SWE" → swe
    result = service.pathways_view(USER_ID)
    assert result.track is not None and result.track.value == "swe"
    assert result.cards  # swe has seed pathways


def test_unknown_track_param_falls_back_to_profile_track() -> None:
    service = _service()
    _onboard(service, [])
    result = service.pathways_view(USER_ID, track="not-a-real-track")
    assert result.track is not None and result.track.value == "swe"


# --------------------------------------------------------------------------- #
# _pathway_constraints (composition root)
# --------------------------------------------------------------------------- #


def test_constraints_project_only_unfilled_slots() -> None:
    service = _service()
    profile = make_profile(
        [item("Payments service", EvidenceKind.WORK, ["backend-systems"])],
        selection(pathway_id=BACKEND),
    )
    constraints, template = service._pathway_constraints(profile)

    assert constraints is not None and template is not None
    assert constraints.pathway_id == BACKEND
    unfilled = {s.slot_id for s in constraints.unfilled_slots}
    assert "service-depth" not in unfilled  # filled, so not a gap
    assert "data-layer" in unfilled  # empty, so a gap
    # The projection carries the slot's hint verbatim (seed text, never control).
    gap = next(s for s in constraints.unfilled_slots if s.slot_id == "data-layer")
    assert gap.gap_module_hint


def test_no_selection_yields_no_shaping() -> None:
    service = _service()
    constraints, template = service._pathway_constraints(make_profile([]))
    assert constraints is None
    assert template is None


def test_stale_version_pin_yields_no_shaping() -> None:
    service = _service()
    stale = selection(pathway_id=BACKEND)
    stale["pathway_registry_version"] = "pathway-registry-v0"
    constraints, template = service._pathway_constraints(make_profile([], stale))
    assert constraints is None
    assert template is None


# --------------------------------------------------------------------------- #
# _pathway_constraints: knowledge-node vocabulary (KT-C)
# --------------------------------------------------------------------------- #


def test_knowledge_node_vocabulary_projected_from_committed_map() -> None:
    service = _service()
    profile = make_profile([], selection(pathway_id=BACKEND))
    constraints, _template = service._pathway_constraints(profile)
    assert constraints is not None

    gmap = knowledge_map_for(BACKEND)
    assert gmap is not None
    expected = {
        n.node_id: n.title
        for n in gmap.nodes
        if n.kind is KnowledgeNodeKind.SKILL
    }
    got = {n.node_id: n.title for n in constraints.knowledge_nodes}
    assert got == expected
    # Capstones are never training targets, so none leak into the vocabulary.
    capstones = {n.node_id for n in gmap.nodes if n.kind is KnowledgeNodeKind.CAPSTONE}
    assert not (got.keys() & capstones)


def test_node_addition_enters_the_vocabulary() -> None:
    service = _service()
    profile = make_profile([], selection(pathway_id=BACKEND))

    gmap = knowledge_map_for(BACKEND)
    assert gmap is not None
    on_map = {n.skill_id for n in gmap.nodes if n.skill_id is not None}
    extra_skill = next(
        e.skill_id
        for e in load_registry().entries_for_track(CareerTrack.SWE)
        if e.skill_id not in on_map
    )
    service._env.knowledge_overlay_store.append(
        NodeAddition(
            user_id=profile.user_id,
            skill_id=extra_skill,
            created_at=datetime(2026, 7, 20, tzinfo=UTC),
        )
    )
    constraints, _template = service._pathway_constraints(profile)
    assert constraints is not None
    assert node_id_for(extra_skill) in {n.node_id for n in constraints.knowledge_nodes}


def test_no_selection_yields_empty_vocabulary() -> None:
    service = _service()
    constraints, _template = service._pathway_constraints(make_profile([]))
    # No selection ⇒ no constraints at all ⇒ the gate's allowed set is empty.
    assert constraints is None
