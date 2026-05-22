"""Region-local exceptions for the Supervisor."""

from __future__ import annotations

from agentic_calendar.common.errors import AgenticCalendarError


class SupervisorError(AgenticCalendarError):
    """Base for every supervisor-internal exception."""


class InvalidTransitionError(SupervisorError):
    """Raised when ``route(state, signal)`` has no allowed next state.

    The exception message includes the ``state`` and ``signal`` values so
    failures land in logs with structured context already attached.
    """

    def __init__(self, state: str, signal: str) -> None:
        self.state = state
        self.signal = signal
        super().__init__(
            f"forbidden supervisor transition: state={state} signal={signal}"
        )
