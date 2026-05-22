"""Pure deterministic routing function.

``route(state, signal)`` is a single dictionary lookup with a typed exception
on a forbidden edge. No I/O, no LLM, no persistence — that lives in the
caller. This keeps the Supervisor easy to unit-test exhaustively (one test
per (state, signal) pair).
"""

from __future__ import annotations

from .errors import InvalidTransitionError
from .state import SupervisorSignal, SupervisorState
from .transitions import TRANSITIONS, VALID_SIGNALS_BY_STATE


def route(state: SupervisorState, signal: SupervisorSignal) -> SupervisorState:
    """Return the next state for the given (state, signal) pair.

    Raises ``InvalidTransitionError`` for any pair not present in
    :data:`agentic_calendar.supervisor.transitions.TRANSITIONS`.
    """
    try:
        return TRANSITIONS[(state, signal)]
    except KeyError as exc:
        raise InvalidTransitionError(state.value, signal.value) from exc


def is_terminal(state: SupervisorState) -> bool:
    """Return ``True`` when ``state`` has no outgoing transitions."""
    return state not in VALID_SIGNALS_BY_STATE


def allowed_signals(state: SupervisorState) -> set[SupervisorSignal]:
    """Return the set of signals that ``state`` accepts (may be empty)."""
    return set(VALID_SIGNALS_BY_STATE.get(state, set()))
