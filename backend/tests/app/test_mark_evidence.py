"""Mark-evidence endpoint: a plain profile edit, no LLM, no invalidation (NP-D-d).

Appends one confirmed evidence item to the profile. Coverage recomputes on read;
the plan is never invalidated (a filled slot only makes a module redundant, which
the next regular replan absorbs). theme_tags stay closed to the track vocabulary.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from agentic_calendar.app.cycle import CycleError
from agentic_calendar.contracts.common_types import EvidenceKind
from tests.app.test_cycle import USER_ID, make_service
from tests.narrative._helpers import item, make_profile

BACKEND = "backend-infrastructure-engineer"


def test_mark_evidence_appends_and_updates_coverage() -> None:
    service, _env, _clock = make_service()  # canonical profile (Backend SWE → swe)
    before = service.pathways_view(USER_ID, track="swe")
    backend_before = next(c for c in before.cards if c.pathway_id == BACKEND)
    assert backend_before.filled_slots == 0

    me = service.mark_evidence(
        USER_ID,
        title="Payments service",
        kind=EvidenceKind.WORK,
        theme_tags=["backend-systems"],
    )
    assert me.profile is not None
    assert me.profile.experience[-1].title == "Payments service"
    assert me.profile.experience[-1].theme_tags == ["backend-systems"]

    after = service.pathways_view(USER_ID, track="swe")
    backend_after = next(c for c in after.cards if c.pathway_id == BACKEND)
    depth = next(s for s in backend_after.slots if s.slot_id == "service-depth")
    assert depth.state.value == "filled"


def test_mark_evidence_does_not_invalidate_active_plan() -> None:
    service, env, _clock = make_service()
    service.propose(USER_ID)
    service.approve(USER_ID)
    service.write(USER_ID)
    active_before = env.plan_store.get_active(USER_ID)
    assert active_before is not None

    service.mark_evidence(USER_ID, title="A project", kind=EvidenceKind.PROJECT)

    active_after = env.plan_store.get_active(USER_ID)
    assert active_after is not None
    assert active_after.plan_version == active_before.plan_version
    assert env.state.get_syllabus(USER_ID) is not None


def test_empty_theme_tags_allowed() -> None:
    service, _env, _clock = make_service()
    me = service.mark_evidence(USER_ID, title="Untagged win", kind=EvidenceKind.AWARD)
    assert me.profile is not None
    assert me.profile.experience[-1].theme_tags == []


def test_off_vocabulary_theme_rejected() -> None:
    service, _env, _clock = make_service()
    with pytest.raises(CycleError, match="theme vocabulary"):
        service.mark_evidence(
            USER_ID, title="X", theme_tags=["not-a-real-theme"]
        )


def test_evidence_cap_enforced_on_rebuild() -> None:
    service, _env, _clock = make_service(onboard=False, seed_claims=False)
    full = make_profile(
        [item(f"Item {i}", EvidenceKind.WORK, []) for i in range(20)]
    )
    service.onboard({"user_profile": full.model_dump(mode="json"), "timezone": "UTC"})
    with pytest.raises(ValidationError):
        service.mark_evidence(USER_ID, title="Overflow", kind=EvidenceKind.WORK)
