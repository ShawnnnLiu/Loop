"""Approval service region.

Owns persistence of :class:`ApprovalEvent` records. Per axiom 06 line 5 the
approval service is distinct from the Calendar Write Manager so the approval
lifecycle is not entangled with the calendar-write lifecycle. The Calendar
Write Manager imports :class:`ApprovalEventStore` via dependency injection.

Allowed dependencies (enforced by ``backend/.importlinter``):
``common``, ``contracts``.
"""

from __future__ import annotations

from .store import (
    ApprovalEventAlreadyExistsError,
    ApprovalEventNotFoundError,
    ApprovalEventStore,
    ApprovalEventStoreError,
    InMemoryApprovalEventStore,
)

__all__ = [
    "ApprovalEventAlreadyExistsError",
    "ApprovalEventNotFoundError",
    "ApprovalEventStore",
    "ApprovalEventStoreError",
    "InMemoryApprovalEventStore",
]
