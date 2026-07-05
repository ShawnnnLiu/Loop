"""Reason-aware resume: persisted prose reaches the status projection (B5),
and persisted reflections feed back as advisory context (D2).

Explanations and reflections used to be one-shot response attachments — a user
returning to a run parked in ERROR_REQUIRES_USER (or a parked replan) saw only
a bare reason code. These tests pin the loop: prose is persisted at the moment
it is generated, ``status`` surfaces the copy for the parked run only
(alongside the typed reason that stays authoritative), and the last few
persisted reflections flow back into the reflection node (continuity) and the
replan Planner (behavioral hints) — advisory prose only, never control-plane.
"""

from __future__ import annotations

from datetime import UTC, datetime

from agentic_calendar.app.environment import AppEnvironment
from agentic_calendar.contracts.checkin_event import RecoveryAction
from agentic_calendar.contracts.task_plan import TaskPlan
from agentic_calendar.llm_nodes.prose_attachment import (
    ProseAttachmentKind,
    ProseAttachmentRecord,
)
from agentic_calendar.supervisor.state import SupervisorState as S
from tests.app.test_cycle import (
    USER_ID,
    RecordingPlanner,
    RecordingReflection,
    _activate_plan,
    _advance_past_draft,
    _canonical_plan,
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


# --------------------------------------------------------------------------- #
# D2: persisted reflections feed back as advisory context
# --------------------------------------------------------------------------- #


def _seed_reflection(env: AppEnvironment, n: int, *, day: int, summary: str) -> None:
    """Append a persisted reflection as an earlier week would have left it."""
    env.prose_store.append(
        ProseAttachmentRecord(
            prose_attachment_id=f"prose_seed_{n:03d}",
            user_id=USER_ID,
            run_id=f"run_seed_{n:03d}",
            kind=ProseAttachmentKind.REFLECTION,
            summary=summary,
            created_at=datetime(2026, 6, day, 9, 0, tzinfo=UTC),
        )
    )


def test_reflection_node_receives_last_three_prior_notes_oldest_first() -> None:
    """The drift-time reflection call carries the last 3 persisted reflection
    summaries (date-prefixed, oldest first) — the continuity context D2's
    prompt builds the 'same coaching conversation' from. The 4th-oldest note
    falls off the window."""
    recording = RecordingReflection()
    service, env, clock = make_service(
        motivation_profile=_motivation_profile_payload(), reflection=recording
    )
    for n, (day, summary) in enumerate(
        [
            (18, "Week one went fine."),
            (19, "Practice tasks ran long."),
            (20, "Two blocks hit calendar conflicts."),
            (21, "Most of the week got done."),
        ],
        start=1,
    ):
        _seed_reflection(env, n, day=day, summary=summary)

    proposed = _activate_plan(service)
    _advance_past_draft(env, clock, proposed.draft_schedule_id)
    result = service.ingest(USER_ID, [_missed_event("evt_001", "dp_001")])
    assert result.reflection is not None

    assert recording.prior[-1] == (
        "2026-06-19: Practice tasks ran long.",
        "2026-06-20: Two blocks hit calendar conflicts.",
        "2026-06-21: Most of the week got done.",
    )


def test_replan_planner_receives_recent_reflections_as_behavioral_hints() -> None:
    """The recovery replan's Planner call carries the same last-3 reflection
    window as behavioral hints — including the reflection the parking ingest
    itself just persisted. The fresh-propose pass carries none (D2 scopes the
    hints to replans)."""
    recording = RecordingPlanner(_canonical_plan())
    payload = {**_motivation_profile_payload(), "recovery_mode_preference": "ask_each_time"}
    service, env, clock = make_service(motivation_profile=payload, planner=recording)
    _seed_reflection(env, 1, day=20, summary="Two blocks hit calendar conflicts.")
    _seed_reflection(env, 2, day=21, summary="Most of the week got done.")

    proposed = _activate_plan(service)
    assert recording.hints[-1] == ()  # fresh propose: no hints block
    _advance_past_draft(env, clock, proposed.draft_schedule_id)

    result = service.ingest(USER_ID, [_missed_event("evt_001", "dp_001")])
    assert result.state is S.REPLAN_REQUIRED
    ingest_note = env.prose_store.latest_for_run(
        result.run_id, kind=ProseAttachmentKind.REFLECTION
    )
    assert ingest_note is not None

    continuation = service.propose(USER_ID, recovery_mode=RecoveryAction.SCOPE_REDUCTION)
    assert continuation.state is S.AWAITING_USER_APPROVAL
    assert recording.hints[-1] == (
        "2026-06-20: Two blocks hit calendar conflicts.",
        "2026-06-21: Most of the week got done.",
        f"{ingest_note.created_at.date().isoformat()}: {ingest_note.summary}",
    )
