"""Calendar event metadata helpers.

Per axiom 06 lines 64-79 and ``docs/specs/calendar-event-mapping.schema.md``
lines 53-68, every event the system creates must carry the four canonical
metadata keys under ``extendedProperties.private``. These helpers build and
verify that dict consistently so the adapter, verifier, and rollback paths all
agree on the contract.
"""

from __future__ import annotations

from collections.abc import Mapping

from .adapter import ExternalEventRecord

APP_TAG = "career_scheduler"


def build_event_metadata(
    *,
    run_id: str,
    plan_version: str,
    task_id: str,
) -> dict[str, str]:
    """Return the canonical metadata dict for a new external calendar event."""
    if not run_id or not plan_version or not task_id:
        raise ValueError("run_id, plan_version, and task_id must all be non-empty")
    return {
        "app": APP_TAG,
        "run_id": run_id,
        "plan_version": plan_version,
        "task_id": task_id,
    }


def verify_event_metadata(
    record: ExternalEventRecord,
    *,
    run_id: str,
    plan_version: str,
    task_id: str,
) -> bool:
    """Return True iff ``record.metadata`` matches the expected app/run/plan/task tuple."""
    md: Mapping[str, str] = record.metadata
    return (
        md.get("app") == APP_TAG
        and md.get("run_id") == run_id
        and md.get("plan_version") == plan_version
        and md.get("task_id") == task_id
    )
