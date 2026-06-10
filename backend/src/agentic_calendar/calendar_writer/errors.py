"""Typed exceptions for the Calendar Write Manager.

Per ``common/errors.py``, every region's public surface raises a region-local
subclass of :class:`AgenticCalendarError`. Each exception here carries the
Phase 2 :class:`ReasonCode` it maps to. Internal helpers
(``CalendarWriteManager._validate_approval``, ``_create_events``,
``_finalize_run``) raise them; the manager catches
:class:`CalendarWriterError` at its public boundary and translates each into
the matching ``WriteResult`` status via
``CalendarWriteManager._translate_error``.

Verification and rollback failures are intentionally NOT exceptions: a
partially-verified or partially-rolled-back run is a normal, queryable
outcome reported per-task in ``VerificationResult`` / ``RollbackResult``
(with ``CALENDAR_VERIFICATION_FAILED`` / ``CALENDAR_ROLLBACK_FAILED`` reason
codes), not an abort of the flow.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from agentic_calendar.common.errors import AgenticCalendarError
from agentic_calendar.contracts.reason_codes import ReasonCode

if TYPE_CHECKING:
    from agentic_calendar.contracts.calendar_event_mapping import (
        CalendarEventMapping,
    )

    from .verification import VerificationResult


class CalendarWriterError(AgenticCalendarError):
    """Base for every Calendar Write Manager exception.

    ``reason_code`` is the typed code the boundary translation uses.
    ``written`` / ``verification`` carry partial-progress state for
    post-write failures so the translated ``WriteResult`` stays lossless.
    """

    reason_code: ClassVar[ReasonCode] = ReasonCode.CALENDAR_WRITE_FAILED

    def __init__(
        self,
        message: str,
        *,
        written: tuple[CalendarEventMapping, ...] = (),
        verification: VerificationResult | None = None,
    ) -> None:
        super().__init__(message)
        self.written = tuple(written)
        self.verification = verification


class ApprovalMissingError(CalendarWriterError):
    """No matching ``ApprovalEvent`` found for ``approval_event_id``."""

    reason_code: ClassVar[ReasonCode] = ReasonCode.APPROVAL_MISSING


class ApprovalExpiredError(CalendarWriterError):
    """Approval's ``expires_at`` ≤ ``clock.now()`` at write time."""

    reason_code: ClassVar[ReasonCode] = ReasonCode.APPROVAL_EXPIRED


class ApprovalHashMismatchError(CalendarWriterError):
    """Recomputed payload hash does not equal the recorded approved hash. **P1.**"""

    reason_code: ClassVar[ReasonCode] = ReasonCode.APPROVAL_HASH_MISMATCH


class ApprovalHashAlgorithmUnsupportedError(CalendarWriterError):
    """Approval's hash algorithm or canonicalization version is not registered."""

    reason_code: ClassVar[ReasonCode] = (
        ReasonCode.APPROVAL_HASH_ALGORITHM_UNSUPPORTED
    )


class CalendarWriteFailedError(CalendarWriterError):
    """Adapter ``create_event`` raised (or the lock heartbeat expired) mid-loop;
    one or more events did not write. Carries the mappings written so far."""

    reason_code: ClassVar[ReasonCode] = ReasonCode.CALENDAR_WRITE_FAILED


class ExternalSyncFailedError(CalendarWriterError):
    """Partial-failure terminal; some events confirmed missing after
    verification. No auto-retry. Carries written mappings + verification."""

    reason_code: ClassVar[ReasonCode] = ReasonCode.EXTERNAL_SYNC_FAILED
