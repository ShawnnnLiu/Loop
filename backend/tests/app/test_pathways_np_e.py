"""Service-layer tests for the NP-E story-layer surfaces.

Three new CycleService methods back the frontend story layer, each staying
deterministic and inside an already-established posture:

* ``preview_pathways`` - persistence-free coverage over a *draft* profile, so
  the onboarding wizard's "Your story" step can rank cards before anything is
  saved (the ``extract_resume`` posture).
* ``evidence_vocabulary_view`` - the closed kind/theme dropdowns, resolved from
  the registry, requiring no onboarding.
* ``select_pathway`` - a targeted selection mutation that changes only
  ``pathway_selection`` (the accountability contract and every other profile
  field are preserved), reusing the onboard invalidation on a pathway change.
"""

from __future__ import annotations

from typing import Any

import pytest

from agentic_calendar.app.cycle import CycleError, CycleService
from agentic_calendar.contracts.common_types import EvidenceKind
from tests.app.test_cycle import (
    USER_ID,
    _canonical_profile,
    _motivation_profile_payload,
    make_service,
)
from tests.narrative._helpers import item

BACKEND = "backend-infrastructure-engineer"
FULLSTACK = "full-stack-product-engineer"


def _draft(experience: list[dict[str, Any]]) -> dict[str, Any]:
    """A draft profile dump (canonical fields + the given evidence)."""
    dump = _canonical_profile().model_dump(mode="json")
    dump["experience"] = experience
    return dump


def _fresh() -> CycleService:
    service, _env, _clock = make_service(onboard=False, seed_claims=False)
    return service


# --------------------------------------------------------------------------- #
# preview_pathways (persistence-free draft coverage)
# --------------------------------------------------------------------------- #


def test_preview_ranks_draft_evidence_and_persists_nothing() -> None:
    # Canonical user is onboarded with NO evidence; the draft carries a work item
    # that fills backend-infra's service-depth slot.
    service, _env, _clock = make_service()
    draft = _draft([item("Payments service", EvidenceKind.WORK, ["backend-systems"])])

    preview = service.preview_pathways(
        USER_ID, {"user_profile": draft, "track": "swe"}
    )
    backend = next(c for c in preview.cards if c.pathway_id == BACKEND)
    assert backend.filled_slots >= 1
    depth = next(s for s in backend.slots if s.slot_id == "service-depth")
    assert depth.state.value == "filled"

    # Nothing was written: the STORED (evidence-free) profile still reads empty.
    stored = service.pathways_view(USER_ID, track="swe")
    assert all(card.filled_slots == 0 for card in stored.cards)


def test_preview_matches_saved_profile_byte_for_byte() -> None:
    # A draft and a saved profile with identical evidence must produce identical
    # cards - preview and the persisted read share one code path.
    service, _env, _clock = make_service()
    exp = [item("Payments service", EvidenceKind.WORK, ["backend-systems"])]
    preview = service.preview_pathways(
        USER_ID, {"user_profile": _draft(exp), "track": "swe"}
    )
    service.mark_evidence(
        USER_ID,
        title="Payments service",
        kind=EvidenceKind.WORK,
        theme_tags=["backend-systems"],
    )
    saved = service.pathways_view(USER_ID, track="swe")
    assert preview.model_dump() == saved.model_dump()


def test_preview_requires_no_onboarding() -> None:
    service = _fresh()  # nothing stored at all
    preview = service.preview_pathways(
        USER_ID,
        {
            "user_profile": _draft(
                [item("Payments service", EvidenceKind.WORK, ["backend-systems"])]
            ),
            "track": "swe",
        },
    )
    assert any(c.filled_slots >= 1 for c in preview.cards)


def test_preview_forces_acting_user() -> None:
    service = _fresh()
    draft = _draft([])
    draft["user_id"] = "someone-else"
    preview = service.preview_pathways(USER_ID, {"user_profile": draft})
    # The result is computed; no record was created for the spoofed id.
    assert preview.registry_version == "pathway-registry-v1"
    assert service._env.state.get_onboarding("someone-else") is None


# --------------------------------------------------------------------------- #
# evidence_vocabulary_view (closed kind/theme dropdowns)
# --------------------------------------------------------------------------- #


def test_vocab_resolves_theme_slice_from_role() -> None:
    service = _fresh()  # no onboarding needed
    vocab = service.evidence_vocabulary_view(USER_ID, role="Backend SWE")
    assert vocab.track is not None and vocab.track.value == "swe"
    assert list(vocab.kinds) == list(EvidenceKind)
    assert "backend-systems" in vocab.themes


def test_vocab_falls_back_to_profile_role() -> None:
    service, _env, _clock = make_service()  # canonical role "Backend SWE"
    vocab = service.evidence_vocabulary_view(USER_ID)
    assert vocab.track is not None and vocab.track.value == "swe"
    assert vocab.themes


def test_vocab_empty_theme_slice_when_no_track_resolves() -> None:
    service = _fresh()
    vocab = service.evidence_vocabulary_view(USER_ID, role="Astronaut")
    assert vocab.track is None
    assert vocab.themes == []
    # Kinds are the fixed enum regardless of track.
    assert list(vocab.kinds) == list(EvidenceKind)


# --------------------------------------------------------------------------- #
# select_pathway (targeted selection mutation)
# --------------------------------------------------------------------------- #


def test_select_from_none_invalidates_plan_but_keeps_contract() -> None:
    motivation = _motivation_profile_payload()
    service, env, _clock = make_service(motivation_profile=motivation)
    service.set_inbound_calendar_sync(USER_ID, enabled=True)
    prior = env.state.get_onboarding(USER_ID)
    assert prior is not None

    service.propose(USER_ID)
    service.approve(USER_ID)
    service.write(USER_ID)
    assert env.plan_store.get_active(USER_ID) is not None

    me = service.select_pathway(USER_ID, pathway_id=BACKEND)
    assert me.profile is not None
    assert me.profile.pathway_selection is not None
    assert me.profile.pathway_selection.pathway_id == BACKEND
    # Selecting from none is a change → the active plan + syllabus are invalidated.
    assert env.plan_store.get_active(USER_ID) is None
    assert env.state.get_syllabus(USER_ID) is None

    # Everything the mutation must NOT touch survives.
    stored = env.state.get_onboarding(USER_ID)
    assert stored is not None
    assert stored.motivation_profile is not None  # accountability contract kept
    assert stored.inbound_calendar_sync_enabled is True  # opt-in kept
    assert stored.created_at == prior.created_at  # not a fresh record


def test_change_pathway_invalidates_active_plan() -> None:
    service, env, _clock = make_service()
    service.select_pathway(USER_ID, pathway_id=BACKEND)
    service.propose(USER_ID)
    service.approve(USER_ID)
    service.write(USER_ID)
    assert env.plan_store.get_active(USER_ID) is not None

    service.select_pathway(USER_ID, pathway_id=FULLSTACK)
    assert env.plan_store.get_active(USER_ID) is None


def test_reselect_same_pathway_keeps_plan() -> None:
    service, env, _clock = make_service()
    service.select_pathway(USER_ID, pathway_id=BACKEND)
    service.propose(USER_ID)
    service.approve(USER_ID)
    service.write(USER_ID)
    active_before = env.plan_store.get_active(USER_ID)
    assert active_before is not None

    service.select_pathway(USER_ID, pathway_id=BACKEND)
    active_after = env.plan_store.get_active(USER_ID)
    assert active_after is not None
    assert active_after.plan_version == active_before.plan_version


def test_select_unknown_pathway_raises_and_persists_nothing() -> None:
    service, env, _clock = make_service()
    with pytest.raises(CycleError):
        service.select_pathway(USER_ID, pathway_id="ghost-pathway")
    stored = env.state.get_onboarding(USER_ID)
    assert stored is not None and stored.user_profile.pathway_selection is None
