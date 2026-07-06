"""Recommitment answers + weekly check-in (UX pass B3).

Before this increment the accountability loop asked and never listened:
``request_recommitment`` fired on every direct nudge but ``record_recommitment``
had zero production callers, and no production code ever appended a
``CheckinEvent`` — so ``evaluate_checkin`` saw an empty history and the policy
engine emitted CHECKIN_DUE/MISSED forever. These tests pin both closed loops.

Scenario notes: with the canonical motivation profile (mot_001,
missed-task threshold 2) missing BOTH plan tasks fires the first private-lane
rule → SEND_USER_NUDGE → a recommitment request; the same ingest also fires
DEPENDENCY_BLOCKED drift (dp_002 depends on dp_001), parking a recovery replan
with mode ``reschedule``.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from agentic_calendar.app.cycle import CycleError
from agentic_calendar.app.state import ReplanKind
from agentic_calendar.contracts.checkin_event import RecoveryAction
from agentic_calendar.contracts.reason_codes import ReasonCode
from agentic_calendar.contracts.recommitment import RecommitmentChoice
from agentic_calendar.supervisor.state import SupervisorState as S
from tests.app.test_cycle import (
    USER_ID,
    _activate_plan,
    _advance_past_draft,
    _missed_event,
    _motivation_profile_payload,
    make_service,
)


def _nudged_service():  # type: ignore[no-untyped-def]
    """Drive to: recovery replan parked (reschedule) + open recommitment ask."""
    service, env, clock = make_service(motivation_profile=_motivation_profile_payload())
    proposed = _activate_plan(service)
    _advance_past_draft(env, clock, proposed.draft_schedule_id)
    result = service.ingest(
        USER_ID,
        [_missed_event("evt_001", "dp_001"), _missed_event("evt_002", "dp_002")],
    )
    assert result.recommitment_request_id is not None
    assert result.state is S.REPLAN_REQUIRED
    assert result.recovery_mode is RecoveryAction.RESCHEDULE
    return service, env, clock


def test_accountability_view_exposes_the_open_ask() -> None:
    service, _env, _clock = _nudged_service()
    view = service.accountability_view(USER_ID)
    assert view.open_recommitment_request_id is not None


def test_accountability_view_replays_reflection_history_newest_first() -> None:
    """The view carries the persisted coaching notes (D2) — the same ingest
    that parked the replan wrote one, and a fresh user has none."""
    service, env, _clock = _nudged_service()
    view = service.accountability_view(USER_ID)
    assert len(view.reflection_history) == 1
    latest = env.prose_store.list_for_user(USER_ID)[-1]
    assert view.reflection_history[0].summary == latest.summary
    assert view.reflection_history[0].created_at == latest.created_at
    assert view.reflection_history[0].plan_version == latest.plan_version

    fresh_service, _env2, _clock2 = make_service()
    assert fresh_service.accountability_view(USER_ID).reflection_history == []


def test_recommit_overrides_the_parked_recovery_mode_with_the_users_choice() -> None:
    """The drift mapping picked ``reschedule``; the user answers "revise
    intensity". Their explicit typed choice beats the heuristic — the parked
    replan continues with scope reduction."""
    service, env, _clock = _nudged_service()

    result = service.recommit(USER_ID, RecommitmentChoice.REVISE_INTENSITY)

    assert result.replan_required is True
    assert result.recovery_mode is RecoveryAction.SCOPE_REDUCTION
    assert result.state is S.REPLAN_REQUIRED
    run = env.state.latest_run_for_user(USER_ID)
    assert run is not None and run.recovery_mode is RecoveryAction.SCOPE_REDUCTION

    continuation = service.propose(USER_ID)
    assert continuation.state is S.AWAITING_USER_APPROVAL
    assert continuation.recovery_mode is RecoveryAction.SCOPE_REDUCTION

    # Answer-once: the ask is closed, and the view reflects it.
    assert service.accountability_view(USER_ID).open_recommitment_request_id is None
    with pytest.raises(CycleError, match="no open recommitment request"):
        service.recommit(USER_ID, RecommitmentChoice.KEEP_PLAN)


def test_recommit_from_active_plan_parks_a_recovery_replan() -> None:
    """The full journey: nudge fires, the drift replan is approved and written,
    the plan is active again — and only then the user answers "revise
    timeline". The answer parks a fresh recovery replan (extend-timeline) via
    the typed RECOMMITMENT_ACCEPTED edge; approval still gates the draft."""
    service, env, _clock = _nudged_service()
    service.propose(USER_ID)
    service.approve(USER_ID)
    written = service.write(USER_ID)
    assert written.state is S.ACTIVE_PLAN

    result = service.recommit(USER_ID, RecommitmentChoice.REVISE_TIMELINE)

    assert result.replan_required is True
    assert result.recovery_mode is RecoveryAction.EXTEND_TIMELINE
    assert result.state is S.REPLAN_REQUIRED
    run = env.state.latest_run_for_user(USER_ID)
    assert run is not None
    assert run.state is S.REPLAN_REQUIRED
    assert run.replan_kind is ReplanKind.RECOVERY
    assert run.reason_code is ReasonCode.USER_RECOMMITMENT_REQUIRED

    continuation = service.propose(USER_ID)
    assert continuation.state is S.AWAITING_USER_APPROVAL
    assert continuation.recovery_mode is RecoveryAction.EXTEND_TIMELINE


def test_recommit_keep_plan_records_without_forcing_a_replan() -> None:
    service, _env, _clock = _nudged_service()

    result = service.recommit(USER_ID, RecommitmentChoice.KEEP_PLAN)

    assert result.replan_required is False
    assert result.recovery_mode is None
    # The drift-parked replan recommendation stands — keep_plan is an explicit
    # re-approval of the plan, not a dismissal of the drift signal.
    assert result.state is S.REPLAN_REQUIRED


def test_recommit_without_an_open_ask_is_a_409_class_error() -> None:
    service, _env, _clock = make_service(motivation_profile=_motivation_profile_payload())
    _activate_plan(service)
    with pytest.raises(CycleError, match="no open recommitment request"):
        service.recommit(USER_ID, RecommitmentChoice.KEEP_PLAN)


# --------------------------------------------------------------------------- #
# weekly check-in
# --------------------------------------------------------------------------- #


def test_weekly_checkin_records_counts_and_clears_due() -> None:
    service, env, clock = make_service(motivation_profile=_motivation_profile_payload())
    proposed = _activate_plan(service)
    _advance_past_draft(env, clock, proposed.draft_schedule_id)
    service.checkin(USER_ID, "dp_001", completed=True)

    before = service.accountability_view(USER_ID)
    assert before.checkin_due is True  # nothing has ever been submitted

    result = service.weekly_checkin(USER_ID, blockers="busy work week")

    assert result.checkin_status == "completed"
    assert result.week_end - result.week_start == timedelta(days=6)
    stored = env.checkin_store.list_for_plan(USER_ID, proposed.plan_version)
    assert len(stored) == 1
    assert stored[0].user_reported_blockers == "busy work week"
    assert stored[0].completed_task_count <= stored[0].scheduled_task_count

    after = service.accountability_view(USER_ID)
    assert after.checkin_due is False
    assert after.checkin_status == "completed"


def test_weekly_checkin_requires_motivation_profile_and_active_plan() -> None:
    bare, _env, _clock = make_service()  # no motivation profile
    _activate_plan(bare)
    with pytest.raises(CycleError, match="motivation profile"):
        bare.weekly_checkin(USER_ID)

    opted, _env2, _clock2 = make_service(motivation_profile=_motivation_profile_payload())
    with pytest.raises(CycleError, match="no active plan"):
        opted.weekly_checkin(USER_ID)
