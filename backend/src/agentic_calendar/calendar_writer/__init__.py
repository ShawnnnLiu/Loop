"""Calendar Write Manager region.

Per axiom 06 line 18, this region is the only writer to external calendars.
The Scheduler emits draft schedules only (axiom 06 line 17); this region
turns approved drafts into verified, rollback-capable external events.

Allowed dependencies (enforced by ``backend/.importlinter``):
``common``, ``contracts``, and ``approval`` (for :class:`ApprovalEventStore`).
No other region may be imported.
"""

from __future__ import annotations

from .adapter import (
    ExternalCalendarAdapter,
    ExternalEventHandle,
    ExternalEventRecord,
)
from .errors import (
    ApprovalExpiredError,
    ApprovalHashAlgorithmUnsupportedError,
    ApprovalHashMismatchError,
    ApprovalMissingError,
    CalendarWriteFailedError,
    CalendarWriterError,
    ExternalSyncFailedError,
)
from .google_adapter import GoogleCalendarAdapter
from .in_memory_adapter import FailureModes, InMemoryCalendarAdapter
from .lock import (
    CalendarWriteLockBusyError,
    CalendarWriteLockExpiredError,
    CalendarWriteLockManager,
    LockToken,
)
from .manager import (
    CalendarWriteManager,
    PlannedEvent,
    PreviewResult,
    WriteResult,
    WriteStatus,
)
from .metadata import APP_TAG, build_event_metadata, verify_event_metadata
from .rollback import RollbackResult, rollback_run
from .store import (
    CalendarEventMappingNotFoundError,
    CalendarEventMappingStore,
    CalendarEventMappingStoreError,
    InMemoryCalendarEventMappingStore,
    InvalidStatusTransitionError,
)
from .verification import VerificationResult, verify_run

__all__ = [
    "APP_TAG",
    "ApprovalExpiredError",
    "ApprovalHashAlgorithmUnsupportedError",
    "ApprovalHashMismatchError",
    "ApprovalMissingError",
    "CalendarEventMappingNotFoundError",
    "CalendarEventMappingStore",
    "CalendarEventMappingStoreError",
    "CalendarWriteFailedError",
    "CalendarWriteLockBusyError",
    "CalendarWriteLockExpiredError",
    "CalendarWriteLockManager",
    "CalendarWriteManager",
    "CalendarWriterError",
    "ExternalCalendarAdapter",
    "ExternalEventHandle",
    "ExternalEventRecord",
    "ExternalSyncFailedError",
    "FailureModes",
    "GoogleCalendarAdapter",
    "InMemoryCalendarAdapter",
    "InMemoryCalendarEventMappingStore",
    "InvalidStatusTransitionError",
    "LockToken",
    "PlannedEvent",
    "PreviewResult",
    "RollbackResult",
    "VerificationResult",
    "WriteResult",
    "WriteStatus",
    "build_event_metadata",
    "rollback_run",
    "verify_event_metadata",
    "verify_run",
]
