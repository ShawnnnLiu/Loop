"""Status-level surfacing of a parked replan (UX pass B2).

The backend has long closed the drift→replan loop; the SPA renders from
``/api/status``, so the parked state must be readable there — including the
ask-each-time case, where ``propose`` 409s until the client supplies a
recovery mode. These tests pin that projection end-to-end.
"""

from __future__ import annotations

import pytest

from agentic_calendar.app.cycle import CycleError
from agentic_calendar.app.state import ReplanKind
from agentic_calendar.contracts.checkin_event import RecoveryAction
from agentic_calendar.supervisor.state import SupervisorState as S
from tests.app.test_cycle import (
    USER_ID,
    _activate_plan,
    _advance_past_draft,
    _missed_event,
    _motivation_profile_payload,
    make_service,
)


def test_status_surfaces_pending_recovery_choice_until_mode_supplied() -> None:
    """ask_each_time parks the run with no resolved mode: status must flag it,
    a bare propose must 409, and a mode-supplied propose must continue."""
    payload = {**_motivation_profile_payload(), "recovery_mode_preference": "ask_each_time"}
    service, env, clock = make_service(motivation_profile=payload)
    proposed = _activate_plan(service)
    _advance_past_draft(env, clock, proposed.draft_schedule_id)

    result = service.ingest(USER_ID, [_missed_event("evt_001", "dp_001")])
    assert result.state is S.REPLAN_REQUIRED
    assert result.recovery_mode_pending_user_choice is True

    st = service.status(USER_ID)
    assert st.state is S.REPLAN_REQUIRED
    assert st.replan_kind is ReplanKind.RECOVERY
    assert st.recovery_mode is None
    assert st.recovery_mode_pending_user_choice is True
    assert st.reason_code is not None  # the banner names the typed cause

    with pytest.raises(CycleError, match="recovery mode"):
        service.propose(USER_ID)

    continuation = service.propose(USER_ID, recovery_mode=RecoveryAction.SCOPE_REDUCTION)
    assert continuation.state is S.AWAITING_USER_APPROVAL
    assert continuation.recovery_mode is RecoveryAction.SCOPE_REDUCTION

    resolved = service.status(USER_ID)
    assert resolved.recovery_mode_pending_user_choice is False


def test_status_pending_flag_stays_false_for_resolved_and_recalibration_paths() -> None:
    """A profile with a concrete preference resolves the mode at ingest time —
    the picker must not appear."""
    service, env, clock = make_service(motivation_profile=_motivation_profile_payload())
    proposed = _activate_plan(service)
    _advance_past_draft(env, clock, proposed.draft_schedule_id)

    service.ingest(USER_ID, [_missed_event("evt_001", "dp_001")])
    st = service.status(USER_ID)
    assert st.state is S.REPLAN_REQUIRED
    assert st.recovery_mode is RecoveryAction.RESCHEDULE
    assert st.recovery_mode_pending_user_choice is False
