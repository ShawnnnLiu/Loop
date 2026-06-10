"""Region-local exceptions for the Scheduler.

Internal helpers raise these; the public ``schedule()`` entry point catches
``SchedulerError`` and translates it into a typed, schema-valid
``SchedulerOutput`` (``schedule_status="failed"`` with one ``UnscheduledTask``
per plan task) so no raw exception ever leaves the region (axiom 16). The
translation lives in ``greedy.schedule``; the exception-to-``ReasonCode``
mapping lives here, on each exception class.

``InfeasibleHorizonError`` (a horizon with no usable windows) was removed: a
window-less horizon is not exceptional — the placement loop already produces
per-task ``INSUFFICIENT_WEEKLY_CAPACITY`` failures with richer debug payloads
via ``_promote_capacity_failures``.
"""

from __future__ import annotations

from typing import ClassVar

from agentic_calendar.common.errors import AgenticCalendarError
from agentic_calendar.contracts.reason_codes import ReasonCode


class SchedulerError(AgenticCalendarError):
    """Base for every scheduler-internal exception.

    ``reason_code`` is the typed code the ``schedule()`` boundary uses when
    translating the exception into ``UnscheduledTask`` records.
    """

    reason_code: ClassVar[ReasonCode] = ReasonCode.SCHEDULING_PRECONDITION_FAILED


class HorizonNotTimezoneAwareError(SchedulerError):
    """A horizon datetime reached window enumeration without ``tzinfo``.

    ``SchedulerInput`` rejects naive horizons at construction, so this firing
    means a caller bypassed the input contract; the boundary still translates
    it rather than letting it escape raw.
    """
