"""Structural tests for the ``TRANSITIONS`` table itself.

These complement the per-pair tests in ``test_routing.py`` by checking
table-wide invariants: no orphan target states, no states declared but
unreachable, etc.
"""

from __future__ import annotations

from agentic_calendar.supervisor.state import SupervisorSignal, SupervisorState
from agentic_calendar.supervisor.transitions import (
    TRANSITIONS,
    VALID_SIGNALS_BY_STATE,
)


def test_every_target_is_a_known_state() -> None:
    targets = set(TRANSITIONS.values())
    assert targets <= set(SupervisorState)


def test_every_signal_used_is_known() -> None:
    used = {sig for (_, sig) in TRANSITIONS}
    assert used <= set(SupervisorSignal)


def test_no_state_routes_to_itself_via_advance_signals() -> None:
    """No advance signal (``*_PRODUCED`` / ``VALIDATION_PASSED``) loops back to self."""
    looping_advance = {
        SupervisorSignal.STRATEGIST_OUTPUT_PRODUCED,
        SupervisorSignal.PLANNER_OUTPUT_PRODUCED,
        SupervisorSignal.VALIDATION_PASSED,
        SupervisorSignal.SCHEDULER_SUCCESS,
        SupervisorSignal.USER_APPROVED,
        SupervisorSignal.CALENDAR_WRITE_SUCCEEDED,
    }
    for (state, sig), nxt in TRANSITIONS.items():
        if sig in looping_advance:
            assert nxt is not state, f"{state} -> self via {sig}"


def test_repair_signals_loop_back_to_running_state() -> None:
    pairs = {
        (SupervisorState.STRATEGIST_VALIDATING,
         SupervisorSignal.VALIDATION_FAILED_REPAIRABLE): SupervisorState.STRATEGIST_RUNNING,
        (SupervisorState.PLANNER_VALIDATING,
         SupervisorSignal.VALIDATION_FAILED_REPAIRABLE): SupervisorState.PLANNER_RUNNING,
    }
    for (state, sig), expected in pairs.items():
        assert TRANSITIONS[(state, sig)] is expected


def test_repair_limit_always_routes_to_error_requires_user() -> None:
    for (_, sig), nxt in TRANSITIONS.items():
        if sig is SupervisorSignal.REPAIR_LIMIT_EXCEEDED:
            assert nxt is SupervisorState.ERROR_REQUIRES_USER


def test_unrecoverable_error_routes_every_nonterminal_state_to_user() -> None:
    """The typed panic signal must be available from every non-terminal
    state and must always land on ERROR_REQUIRES_USER; terminals and the
    error state itself stay sinks."""
    sinks = {
        SupervisorState.TERMINAL_SUCCESS,
        SupervisorState.TERMINAL_DISCARDED,
        SupervisorState.ERROR_REQUIRES_USER,
    }
    for state in SupervisorState:
        pair = (state, SupervisorSignal.UNRECOVERABLE_ERROR)
        if state in sinks:
            assert pair not in TRANSITIONS
        else:
            assert TRANSITIONS[pair] is SupervisorState.ERROR_REQUIRES_USER


def test_valid_signals_index_matches_table() -> None:
    rebuilt: dict[SupervisorState, set[SupervisorSignal]] = {}
    for (state, sig), _ in TRANSITIONS.items():
        rebuilt.setdefault(state, set()).add(sig)
    assert rebuilt == VALID_SIGNALS_BY_STATE
