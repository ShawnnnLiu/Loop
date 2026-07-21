"""Composition-root projection of mastery memory into ``StrategyConstraints`` (MM-C).

``_pathway_constraints`` folds the account's overlay records + completion
telemetry into skill mastery (``narrative.mastery_memory``) and projects the
result onto the ``StrategyConstraints`` mastery slice the Strategist is handed.
These tests pin the seam: no selection ⇒ no constraints; a fresh selection ⇒
empty slice + MM-A defaults; a honed node ⇒ it lands in ``mastered_node_ids`` and
resolves to the ``knowledge_nodes`` vocabulary (the contract subset invariant).
"""

from __future__ import annotations

from agentic_calendar.app.cycle import CycleService
from agentic_calendar.contracts.common_types import MasteryTier
from tests.app.test_cycle import USER_ID, make_service
from tests.narrative._helpers import make_profile, selection

BACKEND = "backend-infrastructure-engineer"


def _service_with_selection() -> CycleService:
    service, _env, _clock = make_service(onboard=False, seed_claims=False)
    profile = make_profile([], selection(pathway_id=BACKEND))
    service.onboard(
        {"user_profile": profile.model_dump(mode="json"), "timezone": "UTC"}
    )
    return service


def _profile(service: CycleService):
    return service._require_onboarding(USER_ID).user_profile


def test_no_selection_yields_no_constraints() -> None:
    service, _env, _clock = make_service(onboard=False, seed_claims=False)
    service.onboard(
        {"user_profile": make_profile([]).model_dump(mode="json"), "timezone": "UTC"}
    )
    constraints, template = service._pathway_constraints(_profile(service))
    assert constraints is None and template is None


def test_fresh_selection_has_empty_mastery_slice() -> None:
    service = _service_with_selection()
    constraints, template = service._pathway_constraints(_profile(service))
    assert constraints is not None and template is not None
    assert constraints.mastered_node_ids == []
    assert constraints.review_node_ids == []
    # MM-A defaults carry through unchanged.
    assert constraints.max_review_modules == 2
    assert constraints.max_review_minutes == 60


def test_honed_setpoint_projects_node_into_mastered_slice() -> None:
    service = _service_with_selection()
    skill = next(
        n for n in service.knowledge_map_view(USER_ID).nodes if n.kind == "skill"
    )
    # A set-point to honed rebases the node's basis onto the honed bar → mastered.
    service.set_mastery(USER_ID, node_id=skill.node_id, target_tier=MasteryTier.HONED)

    constraints, _ = service._pathway_constraints(_profile(service))
    assert constraints is not None
    assert skill.node_id in constraints.mastered_node_ids
    assert skill.node_id not in constraints.review_node_ids
    # Every projected id resolves to the knowledge_nodes vocabulary — the
    # composition-time guarantee the contract subset invariant also enforces.
    vocabulary = {n.node_id for n in constraints.knowledge_nodes}
    assert set(constraints.mastered_node_ids) <= vocabulary
    assert set(constraints.review_node_ids) <= vocabulary


def test_setpoint_back_down_reopens_the_node_for_study() -> None:
    # The two closed loops from 08-…: a downward set-point drops the node out of
    # mastered, so the next generation offers it for study again.
    service = _service_with_selection()
    skill = next(
        n for n in service.knowledge_map_view(USER_ID).nodes if n.kind == "skill"
    )
    service.set_mastery(USER_ID, node_id=skill.node_id, target_tier=MasteryTier.HONED)
    constraints, _ = service._pathway_constraints(_profile(service))
    assert constraints is not None and skill.node_id in constraints.mastered_node_ids

    service.set_mastery(
        USER_ID, node_id=skill.node_id, target_tier=MasteryTier.DISCOVERED
    )
    constraints, _ = service._pathway_constraints(_profile(service))
    assert constraints is not None
    assert skill.node_id not in constraints.mastered_node_ids
    assert skill.node_id not in constraints.review_node_ids
