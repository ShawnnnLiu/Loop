"""Rollback of external calendar events created by a run.

Per axiom 06 lines 132-137: rollback uses the stored ``calendar_event_id`` and
metadata, never fuzzy title matching. Every event tagged with the run's
``run_id`` is deleted. Per-event delete failures do NOT abort the rollback —
they're recorded so the manager can mark each mapping appropriately
(``rolled_back`` vs ``rollback_failed``) and surface the partial-failure
state for user attention.

Like verification, rollback is a pure function over (mappings, adapter). The
manager owns the mapping-store mutations.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from agentic_calendar.contracts.calendar_event_mapping import CalendarEventMapping
from agentic_calendar.contracts.reason_codes import ReasonCode

from .adapter import ExternalCalendarAdapter


@dataclass(frozen=True, slots=True)
class RollbackResult:
    """Outcome of rolling back every mapping for one ``run_id``."""

    run_id: str
    deleted_event_ids: tuple[str, ...]
    failed_event_ids: tuple[str, ...]
    fully_rolled_back: bool
    reason_code: ReasonCode | None


def rollback_run(
    *,
    run_id: str,
    mappings: Sequence[CalendarEventMapping],
    adapter: ExternalCalendarAdapter,
    target_calendar_id: str,
) -> RollbackResult:
    """Delete every external event mapped to ``run_id``.

    Mappings without a ``calendar_event_id`` are skipped (nothing external
    to delete). Any adapter ``delete_event`` exception is caught and recorded
    on ``failed_event_ids``; the rollback continues to the remaining events
    so a single bad delete doesn't leave a partially-rolled-back run.
    """
    deleted: list[str] = []
    failed: list[str] = []

    for mapping in mappings:
        if mapping.run_id != run_id:
            continue
        if mapping.calendar_event_id is None:
            # Nothing external to delete (mapping never reached `written`).
            continue
        try:
            adapter.delete_event(
                target_calendar_id=target_calendar_id,
                calendar_event_id=mapping.calendar_event_id,
            )
        except Exception:
            failed.append(mapping.calendar_event_id)
            continue
        deleted.append(mapping.calendar_event_id)

    fully_rolled_back = not failed
    reason_code = None if fully_rolled_back else ReasonCode.CALENDAR_ROLLBACK_FAILED
    return RollbackResult(
        run_id=run_id,
        deleted_event_ids=tuple(deleted),
        failed_event_ids=tuple(failed),
        fully_rolled_back=fully_rolled_back,
        reason_code=reason_code,
    )
