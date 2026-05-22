"""Region-local exceptions for the Scheduler.

Internal helpers may raise these; the public ``schedule()`` function catches
them and translates to a typed ``SchedulerOutput`` so no raw exception ever
leaves the region (axiom 16).
"""

from __future__ import annotations

from agentic_calendar.common.errors import AgenticCalendarError


class SchedulerError(AgenticCalendarError):
    """Base for every scheduler-internal exception."""


class InfeasibleHorizonError(SchedulerError):
    """The horizon contains no usable windows at all."""
