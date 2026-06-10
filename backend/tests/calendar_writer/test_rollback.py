"""Tests for ``calendar_writer/rollback.py`` (Phase 2)."""

from __future__ import annotations

from datetime import UTC, datetime

from agentic_calendar.calendar_writer.in_memory_adapter import (
    FailureModes,
    InMemoryCalendarAdapter,
)
from agentic_calendar.calendar_writer.metadata import build_event_metadata
from agentic_calendar.calendar_writer.rollback import rollback_run
from agentic_calendar.common.ids import DeterministicIdGenerator
from agentic_calendar.contracts.calendar_event_mapping import (
    CalendarEventMapping,
    CalendarWriteStatus,
)
from agentic_calendar.contracts.reason_codes import ReasonCode

_START = datetime(2026, 5, 4, 18, 0, tzinfo=UTC)
_END = datetime(2026, 5, 4, 19, 0, tzinfo=UTC)


def _setup(
    failure_modes: FailureModes | None = None,
    task_ids: tuple[str, ...] = ("t1", "t2"),
) -> tuple[InMemoryCalendarAdapter, list[CalendarEventMapping]]:
    adapter = InMemoryCalendarAdapter(
        id_generator=DeterministicIdGenerator(),
        failure_modes=failure_modes,
    )
    mappings: list[CalendarEventMapping] = []
    for tid in task_ids:
        handle = adapter.create_event(
            target_calendar_id="primary",
            scheduled_start=_START,
            scheduled_end=_END,
            metadata=build_event_metadata(
                run_id="run_001", plan_version="plan_001", task_id=tid
            ),
        )
        mappings.append(
            CalendarEventMapping(
                task_id=tid,
                plan_version="plan_001",
                run_id="run_001",
                calendar_event_id=handle.calendar_event_id,
                scheduled_start=_START,
                scheduled_end=_END,
                calendar_write_status=CalendarWriteStatus.WRITTEN,
                user_modified_bool=False,
                last_verified_at=None,
            )
        )
    return adapter, mappings


def test_full_rollback_deletes_every_event() -> None:
    adapter, mappings = _setup()
    result = rollback_run(
        run_id="run_001",
        mappings=mappings,
        adapter=adapter,
        target_calendar_id="primary",
    )
    assert result.fully_rolled_back
    assert result.reason_code is None
    assert len(result.deleted_event_ids) == 2
    assert result.failed_event_ids == ()
    # Adapter no longer holds the events.
    assert adapter.all_events() == []


def test_rollback_failure_for_one_event_marks_failed() -> None:
    adapter, mappings = _setup()
    failing_id = mappings[0].calendar_event_id
    assert failing_id is not None
    # Re-wire adapter with the failure mode on the first event id.
    adapter.set_failure_modes(
        FailureModes(fail_delete_for_event_ids=frozenset({failing_id}))
    )
    result = rollback_run(
        run_id="run_001",
        mappings=mappings,
        adapter=adapter,
        target_calendar_id="primary",
    )
    assert not result.fully_rolled_back
    assert result.reason_code is ReasonCode.CALENDAR_ROLLBACK_FAILED
    assert failing_id in result.failed_event_ids
    # The other event was still deleted.
    assert mappings[1].calendar_event_id in result.deleted_event_ids


def test_mapping_without_event_id_skipped() -> None:
    adapter = InMemoryCalendarAdapter(id_generator=DeterministicIdGenerator())
    mapping_no_id = CalendarEventMapping(
        task_id="t1",
        plan_version="plan_001",
        run_id="run_001",
        calendar_event_id=None,
        scheduled_start=_START,
        scheduled_end=_END,
        calendar_write_status=CalendarWriteStatus.DRY_RUN,
        user_modified_bool=False,
        last_verified_at=None,
    )
    result = rollback_run(
        run_id="run_001",
        mappings=[mapping_no_id],
        adapter=adapter,
        target_calendar_id="primary",
    )
    assert result.fully_rolled_back
    assert result.deleted_event_ids == ()
    assert result.failed_event_ids == ()


def test_mappings_with_wrong_run_id_skipped() -> None:
    adapter, mappings = _setup()
    foreign = CalendarEventMapping(
        task_id="foreign",
        plan_version="plan_001",
        run_id="OTHER_RUN",
        calendar_event_id="gcal_evt_999",
        scheduled_start=_START,
        scheduled_end=_END,
        calendar_write_status=CalendarWriteStatus.WRITTEN,
        user_modified_bool=False,
        last_verified_at=None,
    )
    result = rollback_run(
        run_id="run_001",
        mappings=[*mappings, foreign],
        adapter=adapter,
        target_calendar_id="primary",
    )
    # Only the two run_001 events were deleted.
    assert len(result.deleted_event_ids) == 2
    assert "gcal_evt_999" not in result.deleted_event_ids


def test_empty_mappings_trivially_succeeds() -> None:
    adapter = InMemoryCalendarAdapter(id_generator=DeterministicIdGenerator())
    result = rollback_run(
        run_id="run_001",
        mappings=[],
        adapter=adapter,
        target_calendar_id="primary",
    )
    assert result.fully_rolled_back
    assert result.deleted_event_ids == ()
    assert result.failed_event_ids == ()


def test_partial_rollback_continues_after_failure() -> None:
    """One failed delete must not abort the rest of the rollback."""
    adapter, mappings = _setup(task_ids=("t1", "t2", "t3"))
    failing_id = mappings[0].calendar_event_id
    assert failing_id is not None
    adapter.set_failure_modes(
        FailureModes(fail_delete_for_event_ids=frozenset({failing_id}))
    )
    result = rollback_run(
        run_id="run_001",
        mappings=mappings,
        adapter=adapter,
        target_calendar_id="primary",
    )
    # Two events deleted, one failed.
    assert len(result.deleted_event_ids) == 2
    assert len(result.failed_event_ids) == 1
