"""Tests for ``calendar_writer/verification.py`` (Phase 2)."""

from __future__ import annotations

from datetime import UTC, datetime

from agentic_calendar.calendar_writer.in_memory_adapter import (
    FailureModes,
    InMemoryCalendarAdapter,
)
from agentic_calendar.calendar_writer.metadata import build_event_metadata
from agentic_calendar.calendar_writer.verification import verify_run
from agentic_calendar.common.clock import FrozenClock
from agentic_calendar.common.ids import DeterministicIdGenerator
from agentic_calendar.contracts.calendar_event_mapping import (
    CalendarEventMapping,
    CalendarWriteStatus,
)
from agentic_calendar.contracts.reason_codes import ReasonCode

_START = datetime(2026, 5, 4, 18, 0, tzinfo=UTC)
_END = datetime(2026, 5, 4, 19, 0, tzinfo=UTC)
_NOW = datetime(2026, 5, 4, 17, 55, tzinfo=UTC)


def _setup(
    failure_modes: FailureModes | None = None,
) -> tuple[InMemoryCalendarAdapter, list[CalendarEventMapping]]:
    adapter = InMemoryCalendarAdapter(
        id_generator=DeterministicIdGenerator(),
        failure_modes=failure_modes,
    )
    mappings: list[CalendarEventMapping] = []
    for tid in ("t1", "t2"):
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


def test_all_verified_happy_path() -> None:
    adapter, mappings = _setup()
    result = verify_run(
        run_id="run_001",
        expected_mappings=mappings,
        adapter=adapter,
        target_calendar_id="primary",
        clock=FrozenClock(_NOW),
    )
    assert result.all_verified
    assert set(result.verified_task_ids) == {"t1", "t2"}
    assert result.failed_task_ids == ()
    assert result.reason_codes_by_task == {}
    assert result.verified_at == _NOW


def test_missing_event_yields_external_sync_failed() -> None:
    """drop_silently makes ``create_event`` succeed but no record stored,
    so verify can't read it back."""
    adapter, mappings = _setup(
        failure_modes=FailureModes(drop_silently_for_task_ids=frozenset({"t1"}))
    )
    result = verify_run(
        run_id="run_001",
        expected_mappings=mappings,
        adapter=adapter,
        target_calendar_id="primary",
        clock=FrozenClock(_NOW),
    )
    assert not result.all_verified
    assert "t1" in result.failed_task_ids
    assert result.reason_codes_by_task["t1"] is ReasonCode.EXTERNAL_SYNC_FAILED


def test_metadata_mismatch_yields_verification_failed() -> None:
    adapter, mappings = _setup(
        failure_modes=FailureModes(corrupt_metadata_for_task_ids=frozenset({"t1"}))
    )
    result = verify_run(
        run_id="run_001",
        expected_mappings=mappings,
        adapter=adapter,
        target_calendar_id="primary",
        clock=FrozenClock(_NOW),
    )
    assert not result.all_verified
    assert "t1" in result.failed_task_ids
    assert result.reason_codes_by_task["t1"] is ReasonCode.CALENDAR_VERIFICATION_FAILED


def test_time_mismatch_yields_verification_failed() -> None:
    adapter = InMemoryCalendarAdapter(id_generator=DeterministicIdGenerator())
    handle = adapter.create_event(
        target_calendar_id="primary",
        scheduled_start=_START,
        scheduled_end=_END,
        metadata=build_event_metadata(
            run_id="run_001", plan_version="plan_001", task_id="t1"
        ),
    )
    drifted_mapping = CalendarEventMapping(
        task_id="t1",
        plan_version="plan_001",
        run_id="run_001",
        calendar_event_id=handle.calendar_event_id,
        # Mapping says the event runs at 20:00; adapter has it at 18:00.
        scheduled_start=datetime(2026, 5, 4, 20, 0, tzinfo=UTC),
        scheduled_end=datetime(2026, 5, 4, 21, 0, tzinfo=UTC),
        calendar_write_status=CalendarWriteStatus.WRITTEN,
        user_modified_bool=False,
        last_verified_at=None,
    )
    result = verify_run(
        run_id="run_001",
        expected_mappings=[drifted_mapping],
        adapter=adapter,
        target_calendar_id="primary",
        clock=FrozenClock(_NOW),
    )
    assert "t1" in result.failed_task_ids
    assert result.reason_codes_by_task["t1"] is ReasonCode.CALENDAR_VERIFICATION_FAILED


def test_mapping_without_calendar_event_id_is_external_sync_failed() -> None:
    adapter = InMemoryCalendarAdapter(id_generator=DeterministicIdGenerator())
    mapping = CalendarEventMapping(
        task_id="t1",
        plan_version="plan_001",
        run_id="run_001",
        calendar_event_id=None,
        scheduled_start=_START,
        scheduled_end=_END,
        calendar_write_status=CalendarWriteStatus.WRITTEN,
        user_modified_bool=False,
        last_verified_at=None,
    )
    result = verify_run(
        run_id="run_001",
        expected_mappings=[mapping],
        adapter=adapter,
        target_calendar_id="primary",
        clock=FrozenClock(_NOW),
    )
    assert result.failed_task_ids == ("t1",)
    assert result.reason_codes_by_task["t1"] is ReasonCode.EXTERNAL_SYNC_FAILED


def test_mappings_with_wrong_run_id_skipped() -> None:
    adapter, mappings = _setup()
    foreign = CalendarEventMapping(
        task_id="foreign",
        plan_version="plan_001",
        run_id="OTHER_RUN",
        calendar_event_id="gcal_evt_x",
        scheduled_start=_START,
        scheduled_end=_END,
        calendar_write_status=CalendarWriteStatus.WRITTEN,
        user_modified_bool=False,
        last_verified_at=None,
    )
    result = verify_run(
        run_id="run_001",
        expected_mappings=[*mappings, foreign],
        adapter=adapter,
        target_calendar_id="primary",
        clock=FrozenClock(_NOW),
    )
    # The foreign mapping is not in the verified or failed lists.
    assert "foreign" not in result.verified_task_ids
    assert "foreign" not in result.failed_task_ids


def test_empty_mappings_is_trivially_verified() -> None:
    adapter = InMemoryCalendarAdapter(id_generator=DeterministicIdGenerator())
    result = verify_run(
        run_id="run_001",
        expected_mappings=[],
        adapter=adapter,
        target_calendar_id="primary",
        clock=FrozenClock(_NOW),
    )
    assert result.all_verified
    assert result.verified_task_ids == ()
    assert result.failed_task_ids == ()
