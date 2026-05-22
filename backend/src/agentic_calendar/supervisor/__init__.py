"""Deterministic Supervisor: pure routing + state enum + transition table.

The Supervisor must not call an LLM, write to the calendar, or mutate core
plan objects. See ``docs/axioms/02-state-machine.md``.
"""

from .errors import InvalidTransitionError, SupervisorError
from .routing import allowed_signals, is_terminal, route
from .state import SupervisorSignal, SupervisorState
from .transitions import TRANSITIONS, VALID_SIGNALS_BY_STATE

__all__ = [
    "TRANSITIONS",
    "VALID_SIGNALS_BY_STATE",
    "InvalidTransitionError",
    "SupervisorError",
    "SupervisorSignal",
    "SupervisorState",
    "allowed_signals",
    "is_terminal",
    "route",
]
