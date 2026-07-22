"""Additive atlas signals on the knowledge-map view (Star Atlas SA-A).

Every signal is a deterministic, server-computed presentation flourish over data
the service already holds - never a score, never an LLM, never a routing input
(axiom 00 / 11). These tests pin each signal's computation and its graceful
degradation: a signal absent for a node (no scheduled session, no evidence, no
self-assessment) drops its flourish and is never fabricated. The honest-count /
tier invariants of ``test_knowledge_map_view`` are unchanged - SA-A only adds
read fields.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from agentic_calendar.app.cycle import CycleService
from agentic_calendar.contracts.common_types import (
    EvidenceKind,
    MasteryGrantSource,
    MasteryTier,
)
from agentic_calendar.contracts.knowledge_map_overlay import CustomNode, MasteryGrant
from agentic_calendar.contracts.syllabus_units import SyllabusUnits
from agentic_calendar.contracts.task_plan import TaskPlan
from agentic_calendar.contracts.telemetry import (
    DataQuality,
    SolveConfidence,
    TelemetryEvent,
)
from agentic_calendar.planning.plan_version import LifecycleState, PlanVersion
from tests._fixture_loader import iter_valid
from tests.app.test_cycle import (
    USER_ID,
    _activate_plan,
    make_service,
)
from tests.narrative._helpers import item, make_profile, selection

BACKEND = "backend-infrastructure-engineer"
_T0 = datetime(2026, 7, 20, 12, 0, tzinfo=UTC)


def _backend_service(experience: list[dict[str, Any]] | None = None) -> CycleService:
    service, _env, _clock = make_service(onboard=False, seed_claims=False)
    profile = make_profile(experience or [], selection(pathway_id=BACKEND))
    service.onboard(
        {"user_profile": profile.model_dump(mode="json"), "timezone": "UTC"}
    )
    return service


def _first_skill(view: Any) -> Any:
    return next(n for n in view.nodes if n.kind == "skill")


# --------------------------------------------------------------------------- #
# A fresh map lights no flourish (the degradation contract at rest)
# --------------------------------------------------------------------------- #


def test_fresh_map_carries_no_atlas_signals() -> None:
    service = _backend_service()
    view = service.knowledge_map_view(USER_ID)
    assert view.nodes  # a real pathway has nodes
    for node in view.nodes:
        assert node.sessions_total is None
        assert node.sessions_done is None
        assert node.next_session_at is None
        assert node.evidence_label is None
        assert node.evidence_confirmed_at is None
        assert node.review_flagged is False
        assert node.self_assessed is False


def test_capstone_and_custom_never_carry_session_fields() -> None:
    service = _backend_service()
    service._env.knowledge_overlay_store.append(
        CustomNode(
            user_id=USER_ID,
            custom_node_id="kcn-thing",
            name="My thing",
            group_id="kg-anything",
            created_at=_T0,
        )
    )
    view = service.knowledge_map_view(USER_ID)
    non_skill = [n for n in view.nodes if n.kind in {"capstone", "custom"}]
    assert non_skill
    for node in non_skill:
        assert node.sessions_total is None
        assert node.sessions_done is None
        assert node.next_session_at is None


# --------------------------------------------------------------------------- #
# self_assessed: a set-point that lifts the tier above earned study
# --------------------------------------------------------------------------- #


def test_setpoint_up_marks_only_that_node_self_assessed() -> None:
    service = _backend_service()
    skill = _first_skill(service.knowledge_map_view(USER_ID))
    view = service.set_mastery(
        USER_ID, node_id=skill.node_id, target_tier=MasteryTier.HONED
    )
    lifted = next(n for n in view.nodes if n.node_id == skill.node_id)
    assert lifted.self_assessed is True
    # No other node is self-assessed by one node's set-point.
    assert all(
        n.self_assessed is False for n in view.nodes if n.node_id != skill.node_id
    )


def test_downward_setpoint_is_not_self_assessed() -> None:
    # A set-point that only *lowers* a node is not a self-claimed higher tier.
    service = _backend_service()
    skill = _first_skill(service.knowledge_map_view(USER_ID))
    service.set_mastery(USER_ID, node_id=skill.node_id, target_tier=MasteryTier.HONED)
    view = service.set_mastery(
        USER_ID, node_id=skill.node_id, target_tier=MasteryTier.DISCOVERED
    )
    node = next(n for n in view.nodes if n.node_id == skill.node_id)
    assert node.tier is MasteryTier.DISCOVERED
    assert node.self_assessed is False


def test_custom_setpoint_up_is_self_assessed() -> None:
    service = _backend_service()
    service._env.knowledge_overlay_store.append(
        CustomNode(
            user_id=USER_ID,
            custom_node_id="kcn-thing",
            name="My thing",
            group_id="kg-anything",
            created_at=_T0,
        )
    )
    view = service.set_mastery(
        USER_ID, node_id="kcn-thing", target_tier=MasteryTier.HONED
    )
    node = next(n for n in view.nodes if n.node_id == "kcn-thing")
    assert node.tier is MasteryTier.HONED
    assert node.self_assessed is True


# --------------------------------------------------------------------------- #
# evidence: skill mark-evidence anchor vs capstone confirmed-experience label
# --------------------------------------------------------------------------- #


def test_skill_mark_evidence_sets_confirmed_at_without_a_label() -> None:
    service = _backend_service()
    skill = _first_skill(service.knowledge_map_view(USER_ID))
    service.set_mastery(USER_ID, node_id=skill.node_id, target_tier=MasteryTier.HONED)
    view = service.mark_node_evidence(USER_ID, node_id=skill.node_id)
    node = next(n for n in view.nodes if n.node_id == skill.node_id)
    assert node.tier is MasteryTier.PROVEN
    assert node.evidence_confirmed_at is not None
    # Mark-evidence stores no label - only the anchor's timestamp is honest.
    assert node.evidence_label is None


def test_capstone_evidence_label_is_the_matched_experience_title() -> None:
    # A backend-systems work item fills backend-infra's "service-depth" slot.
    service = _backend_service(
        [item("Payments service", EvidenceKind.WORK, ["backend-systems"])]
    )
    view = service.knowledge_map_view(USER_ID)
    branch = next(b for b in view.branches if b.slot_id == "service-depth")
    capstone = next(n for n in view.nodes if n.node_id == branch.capstone_node_id)
    assert capstone.tier is MasteryTier.PROVEN
    assert capstone.evidence_label == "Payments service"
    # Experience items carry no timestamp, so a capstone has no confirmed_at.
    assert capstone.evidence_confirmed_at is None


def test_unproven_capstone_has_no_evidence_label() -> None:
    service = _backend_service()
    view = service.knowledge_map_view(USER_ID)
    capstones = [n for n in view.nodes if n.kind == "capstone"]
    assert capstones and all(c.tier is MasteryTier.DISCOVERED for c in capstones)
    assert all(c.evidence_label is None for c in capstones)


# --------------------------------------------------------------------------- #
# _evidence_grant_times: latest evidence-source grant per node (unit)
# --------------------------------------------------------------------------- #


def test_evidence_grant_times_takes_latest_evidence_source_only() -> None:
    t1 = datetime(2026, 7, 1, tzinfo=UTC)
    t2 = datetime(2026, 7, 5, tzinfo=UTC)
    grants = [
        MasteryGrant(
            user_id=USER_ID,
            node_id="kn-a",
            credit_minutes=10,
            source=MasteryGrantSource.ONBOARDING,
            created_at=t2,  # newer, but not evidence: must be ignored
        ),
        MasteryGrant(
            user_id=USER_ID,
            node_id="kn-a",
            credit_minutes=10,
            source=MasteryGrantSource.EVIDENCE,
            created_at=t1,
        ),
        MasteryGrant(
            user_id=USER_ID,
            node_id="kn-a",
            credit_minutes=10,
            source=MasteryGrantSource.EVIDENCE,
            created_at=t2,  # newer evidence wins
        ),
    ]
    times = CycleService._evidence_grant_times(grants)
    assert times == {"kn-a": t2}


# --------------------------------------------------------------------------- #
# session signals: active-plan counts + next upcoming start
# --------------------------------------------------------------------------- #


def _completed(task_id: str, *, minutes: int, at: datetime, conf: Any = None) -> Any:
    return TelemetryEvent(
        telemetry_event_id=f"t_{task_id}_{int(at.timestamp())}",
        task_id=task_id,
        scheduled_duration_min=minutes,
        actual_duration_min=minutes,
        completed=True,
        completion_timestamp=at,
        user_reschedule_count=0,
        data_quality=DataQuality.COMPLETE,
        solve_confidence=conf,
    )


def _plan_004() -> TaskPlan:
    payload = next(
        f.payload for f in iter_valid("task_plan") if f.payload["plan_version"] == "plan_004"
    )
    return TaskPlan.model_validate(payload)


def test_session_signals_count_scheduled_done_and_next() -> None:
    service, env, clock = make_service()
    _activate_plan(service)  # active plan: dp_001, dp_002, both module "dp"

    # Link module "dp" to a knowledge node so the projection has a target.
    stored = env.state.get_syllabus(USER_ID)
    assert stored is not None
    dump = stored.model_dump()
    for module in dump["modules"]:
        if module["module_id"] == "dp":
            module["knowledge_node_ids"] = ["kn-alpha"]
    env.state.save_syllabus(USER_ID, SyllabusUnits.model_validate(dump))

    # dp_001 has a completed telemetry event; dp_002 does not.
    env.telemetry_store.append(
        _completed("dp_001", minutes=60, at=clock.now() - timedelta(hours=1))
    )

    draft = service._active_draft(USER_ID)
    assert draft is not None
    now = clock.now()
    starts = {e.task_id: e.start for e in draft.entries}
    upcoming = [s for tid, s in starts.items() if tid in {"dp_001", "dp_002"} and s > now]
    expected_next = min(upcoming) if upcoming else None

    signals = service._session_signals(USER_ID)
    assert signals["kn-alpha"] == (2, 1, expected_next)


def test_session_signals_empty_without_an_active_plan() -> None:
    service, _env, _clock = make_service()  # onboarded, but no plan activated
    assert service._session_signals(USER_ID) == {}


# --------------------------------------------------------------------------- #
# review_flagged: honed on raw minutes, not on the confidence-weighted basis
# --------------------------------------------------------------------------- #


def test_low_confidence_completion_review_flags_its_node() -> None:
    service = _backend_service()
    env = service._env
    view = service.knowledge_map_view(USER_ID)
    target = next(
        n for n in view.nodes if n.kind == "skill" and (n.expected_minutes or 0) > 0
    )
    other = next(
        n
        for n in view.nodes
        if n.kind == "skill" and n.node_id != target.node_id
    )
    expected = target.expected_minutes or 0

    # A plan version whose module "dp" trains the target node, plus a completed
    # low-confidence session: full minutes clear the honed bar, but the 0.25
    # needed-help weight drops the weighted basis below it → review-flagged.
    plan = _plan_004()
    env.plan_store.save(
        PlanVersion(
            plan_version=plan.plan_version,
            user_id=USER_ID,
            state=LifecycleState.ACTIVE,
            plan=plan,
            created_at=_T0,
            updated_at=_T0,
        )
    )
    env.state.save_syllabus(
        USER_ID,
        SyllabusUnits.model_validate(
            {
                "syllabus_version": "syl_review",
                "goal_summary": "review-flag fixture",
                "modules": [
                    {
                        "module_id": "dp",
                        "title": "Distributed patterns",
                        "priority": "medium",
                        "target_outcomes": ["outcome"],
                        "estimated_total_min": 120,
                        "difficulty": 3,
                        "knowledge_node_ids": [target.node_id],
                    }
                ],
            }
        ),
    )
    env.telemetry_store.append(
        _completed(
            "dp_001",
            minutes=expected,
            at=_T0,
            conf=SolveConfidence.NEEDED_HELP,
        )
    )

    refreshed = service.knowledge_map_view(USER_ID)
    flagged = next(n for n in refreshed.nodes if n.node_id == target.node_id)
    assert flagged.review_flagged is True
    assert flagged.tier is not MasteryTier.HONED  # the weight kept it under the bar
    # A node with no low-confidence work is not flagged.
    assert next(
        n for n in refreshed.nodes if n.node_id == other.node_id
    ).review_flagged is False
