"""Exhaustive tests for ``supervisor.routing.route``.

Every (state, signal) pair is exercised: the entries in ``TRANSITIONS`` must
return the expected next state; *every* other pair must raise
``InvalidTransitionError``. This is the single best place to enforce
"no LLM-controlled routing": if a future change adds an edge, the test for
that exact pair fails until ``TRANSITIONS`` is updated.
"""

from __future__ import annotations

import pytest

from agentic_calendar.supervisor import (
    InvalidTransitionError,
    SupervisorSignal,
    SupervisorState,
    allowed_signals,
    is_terminal,
    route,
)
from agentic_calendar.supervisor.transitions import TRANSITIONS


@pytest.mark.parametrize(
    ("state", "signal", "expected_next"),
    [(s, sig, nxt) for (s, sig), nxt in TRANSITIONS.items()],
    ids=lambda v: getattr(v, "value", str(v)),
)
def test_every_allowed_transition_returns_expected_next_state(
    state: SupervisorState, signal: SupervisorSignal, expected_next: SupervisorState
) -> None:
    assert route(state, signal) is expected_next


@pytest.mark.parametrize(
    ("state", "signal"),
    [
        (s, sig)
        for s in SupervisorState
        for sig in SupervisorSignal
        if (s, sig) not in TRANSITIONS
    ],
    ids=lambda v: getattr(v, "value", str(v)),
)
def test_every_other_pair_is_forbidden(
    state: SupervisorState, signal: SupervisorSignal
) -> None:
    with pytest.raises(InvalidTransitionError) as exc_info:
        route(state, signal)
    assert exc_info.value.state == state.value
    assert exc_info.value.signal == signal.value


def test_terminal_states_have_no_outgoing_transitions() -> None:
    for terminal in (
        SupervisorState.ERROR_REQUIRES_USER,
        SupervisorState.TERMINAL_SUCCESS,
        SupervisorState.TERMINAL_DISCARDED,
    ):
        assert is_terminal(terminal) is True
        assert allowed_signals(terminal) == set()


def test_initial_only_accepts_user_profile_collected() -> None:
    assert allowed_signals(SupervisorState.INITIAL) == {
        SupervisorSignal.USER_PROFILE_COLLECTED
    }


def test_planner_validating_can_repair_or_advance_or_escalate() -> None:
    assert allowed_signals(SupervisorState.PLANNER_VALIDATING) == {
        SupervisorSignal.VALIDATION_PASSED,
        SupervisorSignal.VALIDATION_FAILED_REPAIRABLE,
        SupervisorSignal.REPAIR_LIMIT_EXCEEDED,
    }


def test_scheduler_full_failure_routes_to_planner_for_repair() -> None:
    assert (
        route(SupervisorState.SCHEDULER_RUNNING, SupervisorSignal.SCHEDULER_FULL_FAILURE)
        is SupervisorState.PLANNER_RUNNING
    )


def test_scheduler_repair_cap_routes_to_error_requires_user() -> None:
    assert (
        route(SupervisorState.SCHEDULER_RUNNING, SupervisorSignal.REPAIR_LIMIT_EXCEEDED)
        is SupervisorState.ERROR_REQUIRES_USER
    )


def test_user_rejected_lands_in_terminal_discarded() -> None:
    assert (
        route(SupervisorState.AWAITING_USER_APPROVAL, SupervisorSignal.USER_REJECTED)
        is SupervisorState.TERMINAL_DISCARDED
    )
