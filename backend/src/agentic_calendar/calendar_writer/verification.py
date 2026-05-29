"""Post-write verification of external calendar events.

Per axiom 06 lines 106 and 124-130: after each event has been created, the
Calendar Write Manager queries the external calendar for that event and
asserts that the metadata (``run_id``/``plan_version``/``task_id``) and the
scheduled times match the local mapping. Any mismatch is recorded as a typed
``ReasonCode`` so the manager can route rollback.

Verification is a pure function over (mappings, adapter) — it doesn't mutate
the mapping store; the manager applies status changes after consuming the
:class:`VerificationResult`.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from agentic_calendar.common.clock import Clock
from agentic_calendar.contracts.calendar_event_mapping import CalendarEventMapping
from agentic_calendar.contracts.reason_codes import ReasonCode

from .adapter import ExternalCalendarAdapter
from .metadata import verify_event_metadata


@dataclass(frozen=True, slots=True)
class VerificationResult:
    """Outcome of verifying every mapping for one ``run_id``."""

    run_id: str
    verified_at: datetime
    verified_task_ids: tuple[str, ...]
    failed_task_ids: tuple[str, ...]
    reason_codes_by_task: dict[str, ReasonCode]
    all_verified: bool


def verify_run(
    *,
    run_id: str,
    expected_mappings: Sequence[CalendarEventMapping],
    adapter: ExternalCalendarAdapter,
    target_calendar_id: str,
    clock: Clock,
) -> VerificationResult:
    """Verify every mapping for ``run_id`` against the adapter.

    For each mapping the verifier checks:

    * a ``calendar_event_id`` exists on the mapping (a mapping without one
      cannot be verified — falls to ``EXTERNAL_SYNC_FAILED``);
    * ``adapter.read_event`` returns a record for that id (missing →
      ``EXTERNAL_SYNC_FAILED``);
    * the record's metadata matches the expected
      ``(run_id, plan_version, task_id)`` (mismatch →
      ``CALENDAR_VERIFICATION_FAILED``);
    * the record's ``scheduled_start`` / ``scheduled_end`` equal the local
      mapping's (mismatch → ``CALENDAR_VERIFICATION_FAILED``).
    """
    verified: list[str] = []
    failed: list[str] = []
    reasons: dict[str, ReasonCode] = {}
    now = clock.now()

    for mapping in expected_mappings:
        if mapping.run_id != run_id:
            # Defensive: the manager passes the correct list, but a future
            # caller might not. Skip rather than misreport.
            continue
        if mapping.calendar_event_id is None:
            failed.append(mapping.task_id)
            reasons[mapping.task_id] = ReasonCode.EXTERNAL_SYNC_FAILED
            continue

        record = adapter.read_event(
            target_calendar_id=target_calendar_id,
            calendar_event_id=mapping.calendar_event_id,
        )
        if record is None:
            failed.append(mapping.task_id)
            reasons[mapping.task_id] = ReasonCode.EXTERNAL_SYNC_FAILED
            continue

        if not verify_event_metadata(
            record,
            run_id=run_id,
            plan_version=mapping.plan_version,
            task_id=mapping.task_id,
        ):
            failed.append(mapping.task_id)
            reasons[mapping.task_id] = ReasonCode.CALENDAR_VERIFICATION_FAILED
            continue

        if (
            record.scheduled_start != mapping.scheduled_start
            or record.scheduled_end != mapping.scheduled_end
        ):
            failed.append(mapping.task_id)
            reasons[mapping.task_id] = ReasonCode.CALENDAR_VERIFICATION_FAILED
            continue

        verified.append(mapping.task_id)

    return VerificationResult(
        run_id=run_id,
        verified_at=now,
        verified_task_ids=tuple(verified),
        failed_task_ids=tuple(failed),
        reason_codes_by_task=reasons,
        all_verified=not failed,
    )
