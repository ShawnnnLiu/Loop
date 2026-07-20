"""Onboard-side pathway selection validation + invalidation (NP-D-c).

Onboarding is the only profile write path, so it owns two service-layer
responsibilities the contract cannot: rejecting a ``pathway_selection`` the
registry cannot honor (typed ``reason_code``, nothing persisted), and
invalidating syllabus + tasks + schedule when the selected pathway changes -
while never resetting evidence or the accountability contract.
"""

from __future__ import annotations

from typing import Any

from agentic_calendar.app.cycle import CycleService
from agentic_calendar.contracts.common_types import EvidenceKind
from agentic_calendar.contracts.reason_codes import ReasonCode
from agentic_calendar.supervisor.state import SupervisorState as S
from tests.app.test_cycle import (
    USER_ID,
    _canonical_profile,
    _motivation_profile_payload,
    make_service,
)
from tests.narrative._helpers import item, make_profile, selection

BACKEND = "backend-infrastructure-engineer"
FULLSTACK = "full-stack-product-engineer"


def _onboard(
    service: CycleService,
    profile_dump: dict[str, Any],
    motivation: dict[str, Any] | None = None,
) -> Any:
    payload: dict[str, Any] = {"user_profile": profile_dump, "timezone": "UTC"}
    if motivation is not None:
        payload["motivation_profile"] = motivation
    return service.onboard(payload)


def _canonical_with_selection(pathway_selection: dict[str, Any] | None) -> dict[str, Any]:
    dump = _canonical_profile().model_dump(mode="json")
    if pathway_selection is not None:
        dump["pathway_selection"] = pathway_selection
    return dump


# --------------------------------------------------------------------------- #
# selection validation (rejected, nothing persisted)
# --------------------------------------------------------------------------- #


def test_unknown_pathway_id_rejected_and_not_persisted() -> None:
    service, env, _clock = make_service(onboard=False, seed_claims=False)
    result = _onboard(
        service, make_profile([], selection(pathway_id="ghost")).model_dump(mode="json")
    )
    assert result.status == "rejected"
    assert result.reason_code is ReasonCode.UNKNOWN_PATHWAY_ID
    assert env.state.get_onboarding(USER_ID) is None


def test_stale_registry_version_rejected() -> None:
    service, env, _clock = make_service(onboard=False, seed_claims=False)
    stale = selection(pathway_id=BACKEND)
    stale["pathway_registry_version"] = "pathway-registry-v0"
    result = _onboard(service, make_profile([], stale).model_dump(mode="json"))
    assert result.status == "rejected"
    assert result.reason_code is ReasonCode.PATHWAY_REGISTRY_VERSION_MISMATCH
    assert env.state.get_onboarding(USER_ID) is None


def test_override_to_unknown_slot_rejected() -> None:
    service, env, _clock = make_service(onboard=False, seed_claims=False)
    exp = [item("Payments", EvidenceKind.WORK, ["backend-systems"], organization="Acme")]
    sel = selection(
        pathway_id=BACKEND,
        slot_overrides=[
            {"item_title": "Payments", "item_organization": "Acme", "slot_id": "ghost-slot"}
        ],
    )
    result = _onboard(service, make_profile(exp, sel).model_dump(mode="json"))
    assert result.status == "rejected"
    assert result.reason_code is ReasonCode.UNKNOWN_EVIDENCE_SLOT
    assert env.state.get_onboarding(USER_ID) is None


def test_valid_selection_persisted() -> None:
    service, env, _clock = make_service(onboard=False, seed_claims=False)
    result = _onboard(
        service, make_profile([], selection(pathway_id=BACKEND)).model_dump(mode="json")
    )
    assert result.status == "ok"
    stored = env.state.get_onboarding(USER_ID)
    assert stored is not None
    assert stored.user_profile.pathway_selection is not None
    assert stored.user_profile.pathway_selection.pathway_id == BACKEND


# --------------------------------------------------------------------------- #
# invalidation on pathway change (full discard)
# --------------------------------------------------------------------------- #


def test_pathway_change_discards_plan_and_syllabus_keeps_contract() -> None:
    motivation = _motivation_profile_payload()
    service, env, _clock = make_service(motivation_profile=motivation)

    # Select a pathway and drive a plan to ACTIVE.
    _onboard(service, _canonical_with_selection(selection(pathway_id=BACKEND)), motivation)
    service.propose(USER_ID)
    service.approve(USER_ID)
    service.write(USER_ID)
    assert env.plan_store.get_active(USER_ID) is not None
    assert env.state.get_syllabus(USER_ID) is not None

    # Change the pathway → syllabus + tasks + schedule invalidated.
    _onboard(service, _canonical_with_selection(selection(pathway_id=FULLSTACK)), motivation)
    assert env.plan_store.get_active(USER_ID) is None
    assert env.state.get_syllabus(USER_ID) is None
    # Evidence + the accountability contract (motivation profile) survive.
    stored = env.state.get_onboarding(USER_ID)
    assert stored is not None and stored.motivation_profile is not None


def test_selecting_from_none_invalidates_existing_plan() -> None:
    service, env, _clock = make_service()  # canonical profile, no selection
    service.propose(USER_ID)
    service.approve(USER_ID)
    service.write(USER_ID)
    assert env.plan_store.get_active(USER_ID) is not None

    _onboard(service, _canonical_with_selection(selection(pathway_id=BACKEND)))
    assert env.plan_store.get_active(USER_ID) is None


def test_same_pathway_reonboard_keeps_plan() -> None:
    service, env, _clock = make_service()
    _onboard(service, _canonical_with_selection(selection(pathway_id=BACKEND)))
    service.propose(USER_ID)
    service.approve(USER_ID)
    service.write(USER_ID)
    active_before = env.plan_store.get_active(USER_ID)
    assert active_before is not None

    # Re-onboard with the SAME pathway (e.g. an unrelated profile edit): no
    # invalidation — a filled slot must not silently wipe the plan.
    _onboard(service, _canonical_with_selection(selection(pathway_id=BACKEND)))
    active_after = env.plan_store.get_active(USER_ID)
    assert active_after is not None
    assert active_after.plan_version == active_before.plan_version


def test_change_retires_awaiting_run_so_stale_draft_is_unapprovable() -> None:
    service, env, _clock = make_service()
    _onboard(service, _canonical_with_selection(selection(pathway_id=BACKEND)))
    proposed = service.propose(USER_ID)
    assert proposed.state is S.AWAITING_USER_APPROVAL

    _onboard(service, _canonical_with_selection(selection(pathway_id=FULLSTACK)))
    latest = env.state.latest_run_for_user(USER_ID)
    assert latest is not None and latest.state is S.TERMINAL_DISCARDED
    # A fresh propose still works (no dead-end).
    assert service.propose(USER_ID).state is S.AWAITING_USER_APPROVAL
