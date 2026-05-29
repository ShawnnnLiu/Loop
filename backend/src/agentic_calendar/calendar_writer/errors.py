"""Typed exceptions for the Calendar Write Manager.

Per ``common/errors.py``, every region's public surface raises a region-local
subclass of :class:`AgenticCalendarError`. Each exception here corresponds to a
Phase 2 :class:`ReasonCode` in ``contracts/reason_codes.py``; the manager
catches at the boundary and translates each to the matching ``WriteResult``
status.
"""

from __future__ import annotations

from agentic_calendar.common.errors import AgenticCalendarError


class CalendarWriterError(AgenticCalendarError):
    """Base for every Calendar Write Manager exception."""


class ApprovalMissingError(CalendarWriterError):
    """No matching ``ApprovalEvent`` found for ``approval_event_id``."""


class ApprovalExpiredError(CalendarWriterError):
    """Approval's ``expires_at`` ≤ ``clock.now()`` at write time."""


class ApprovalHashMismatchError(CalendarWriterError):
    """Recomputed payload hash does not equal the recorded approved hash. **P1.**"""


class ApprovalHashAlgorithmUnsupportedError(CalendarWriterError):
    """Approval's ``hash_canonicalization_version`` is not registered."""


class CalendarWriteFailedError(CalendarWriterError):
    """Adapter ``create_event`` raised; one or more events did not write."""


class CalendarVerificationFailedError(CalendarWriterError):
    """Post-write read-back found mismatched metadata or scheduled times."""


class CalendarRollbackFailedError(CalendarWriterError):
    """Adapter ``delete_event`` raised during rollback; mapping marked rollback_failed."""


class ExternalSyncFailedError(CalendarWriterError):
    """Partial-failure terminal; some events confirmed missing. No auto-retry."""
