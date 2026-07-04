"""Reason-aware resume: persisted prose reaches the status projection (B5).

Explanations and reflections used to be one-shot response attachments — a user
returning to a run parked in ERROR_REQUIRES_USER (or a parked replan) saw only
a bare reason code. These tests pin the loop: prose is persisted at the moment
it is generated, and ``status`` surfaces the copy for the parked run only,
alongside the typed reason that stays authoritative.
"""

from __future__ import annotations

from agentic_calendar.contracts.task_plan import TaskPlan
from agentic_calendar.llm_nodes.prose_attachment import ProseAttachmentKind
from agentic_calendar.supervisor.state import SupervisorState as S
from tests.app.test_cycle import (
    USER_ID,
    _activate_plan,
    _advance_past_draft,
    _missed_event,
    _motivation_profile_payload,
    make_service,
)

_BAD_PLAN = TaskPlan.model_validate(
    {
        "plan_version": "plan_bad",
        "tasks": [
            {
                "task_id": "ghost_001",
                "module_id": "nonexistent",
                "title": "task in a module the syllabus does not define",
                "dependencies": [],
                "estimated_duration_min": 60,
                "cognitive_load": 3,
                "category": "practice",
                "required_focus_level": "medium",
                "splittable": False,
            }
        ],
    }
)


def test_failed_propose_persists_explanation_and_status_replays_it() -> None:
    service, env, _clock = make_service(planner_fixtures={"syl_003": _BAD_PLAN})

    result = service.propose(USER_ID)
    assert result.state is S.ERROR_REQUIRES_USER
    assert result.explanation is not None

    stored = env.prose_store.list_for_run(result.run_id)
    assert [r.kind for r in stored] == [ProseAttachmentKind.EXPLANATION]
    assert stored[0].summary == result.explanation.summary
    assert stored[0].reason_code is result.reason_code

    # The projection replays the prose for the parked run — a returning user
    # sees WHY, not a bare code.
    st = service.status(USER_ID)
    assert st.state is S.ERROR_REQUIRES_USER
    assert st.explanation is not None
    assert st.explanation.summary == result.explanation.summary


def test_drift_reflection_is_persisted_and_surfaces_on_the_parked_replan() -> None:
    service, env, clock = make_service(motivation_profile=_motivation_profile_payload())
    proposed = _activate_plan(service)
    _advance_past_draft(env, clock, proposed.draft_schedule_id)

    result = service.ingest(USER_ID, [_missed_event("evt_001", "dp_001")])
    assert result.state is S.REPLAN_REQUIRED
    assert result.reflection is not None

    stored = env.prose_store.latest_for_run(
        result.run_id, kind=ProseAttachmentKind.REFLECTION
    )
    assert stored is not None
    assert stored.summary == result.reflection.summary

    st = service.status(USER_ID)
    assert st.reflection is not None
    assert st.reflection.summary == result.reflection.summary
    # The explanation slot stays empty — the run is parked on the replan
    # path, not a failure state.
    assert st.explanation is None


def test_prose_is_not_replayed_for_healthy_runs() -> None:
    service, _env, _clock = make_service()
    _activate_plan(service)
    st = service.status(USER_ID)
    assert st.state is S.ACTIVE_PLAN
    assert st.explanation is None
    assert st.reflection is None
