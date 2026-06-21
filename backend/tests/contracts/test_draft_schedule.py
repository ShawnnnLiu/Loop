"""Tests for the ``DraftSchedule`` contract (Phase 2)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from agentic_calendar.contracts.draft_schedule import (
    DraftSchedule,
    DraftScheduleEntry,
)
from agentic_calendar.contracts.reason_codes import ReasonCode
from agentic_calendar.contracts.scheduler_output import (
    CalendarEventStatus,
    RepairOption,
    ScheduledTask,
    SchedulerOutput,
    ScheduleStatus,
    UnscheduledTask,
)


def _entry(
    task_id: str = "dp_001",
    start: datetime = datetime(2026, 5, 4, 18, 0, tzinfo=UTC),
    end: datetime = datetime(2026, 5, 4, 19, 0, tzinfo=UTC),
) -> DraftScheduleEntry:
    return DraftScheduleEntry(task_id=task_id, start=start, end=end)


def _draft(entries: tuple[DraftScheduleEntry, ...] | None = None) -> DraftSchedule:
    return DraftSchedule(
        draft_schedule_id="draft_001",
        plan_version="plan_001",
        entries=entries if entries is not None else (_entry(),),
        created_at=datetime(2026, 5, 4, 17, 55, tzinfo=UTC),
    )


# --------------------------------------------------------------------------- #
# DraftScheduleEntry
# --------------------------------------------------------------------------- #


def test_entry_round_trip() -> None:
    entry = _entry()
    payload = entry.model_dump(mode="json")
    again = DraftScheduleEntry.model_validate(payload)
    assert again == entry


def test_entry_naive_start_rejected() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        DraftScheduleEntry(
            task_id="t",
            start=datetime(2026, 5, 4, 18, 0),  # naive
            end=datetime(2026, 5, 4, 19, 0, tzinfo=UTC),
        )


def test_entry_naive_end_rejected() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        DraftScheduleEntry(
            task_id="t",
            start=datetime(2026, 5, 4, 18, 0, tzinfo=UTC),
            end=datetime(2026, 5, 4, 19, 0),  # naive
        )


def test_entry_end_before_start_rejected() -> None:
    with pytest.raises(ValidationError, match="strictly after"):
        DraftScheduleEntry(
            task_id="t",
            start=datetime(2026, 5, 4, 19, 0, tzinfo=UTC),
            end=datetime(2026, 5, 4, 18, 0, tzinfo=UTC),
        )


def test_entry_end_equal_start_rejected() -> None:
    with pytest.raises(ValidationError, match="strictly after"):
        DraftScheduleEntry(
            task_id="t",
            start=datetime(2026, 5, 4, 18, 0, tzinfo=UTC),
            end=datetime(2026, 5, 4, 18, 0, tzinfo=UTC),
        )


def test_entry_empty_task_id_rejected() -> None:
    with pytest.raises(ValidationError):
        DraftScheduleEntry(
            task_id="",
            start=datetime(2026, 5, 4, 18, 0, tzinfo=UTC),
            end=datetime(2026, 5, 4, 19, 0, tzinfo=UTC),
        )


def test_entry_is_frozen() -> None:
    entry = _entry()
    with pytest.raises(ValidationError):
        entry.task_id = "other"  # type: ignore[misc]


def test_entry_extra_field_rejected() -> None:
    with pytest.raises(ValidationError):
        DraftScheduleEntry.model_validate(
            {
                "task_id": "t",
                "start": "2026-05-04T18:00:00+00:00",
                "end": "2026-05-04T19:00:00+00:00",
                "extra": "nope",
            }
        )


def test_entry_default_calendar_event_status_is_draft_only() -> None:
    entry = _entry()
    assert entry.calendar_event_status is CalendarEventStatus.DRAFT_ONLY


# --------------------------------------------------------------------------- #
# DraftSchedule
# --------------------------------------------------------------------------- #


def test_draft_round_trip() -> None:
    draft = _draft()
    payload = draft.model_dump(mode="json")
    again = DraftSchedule.model_validate(payload)
    assert again == draft


def test_draft_empty_entries_rejected() -> None:
    with pytest.raises(ValidationError, match="at least one entry"):
        DraftSchedule(
            draft_schedule_id="d",
            plan_version="p",
            entries=(),
            created_at=datetime(2026, 5, 4, 17, 55, tzinfo=UTC),
        )


def test_draft_duplicate_task_id_rejected() -> None:
    e1 = _entry(task_id="dup")
    e2 = _entry(
        task_id="dup",
        start=datetime(2026, 5, 4, 20, 0, tzinfo=UTC),
        end=datetime(2026, 5, 4, 21, 0, tzinfo=UTC),
    )
    with pytest.raises(ValidationError, match="more than once"):
        DraftSchedule(
            draft_schedule_id="d",
            plan_version="p",
            entries=(e1, e2),
            created_at=datetime(2026, 5, 4, 17, 55, tzinfo=UTC),
        )


def test_draft_naive_created_at_rejected() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        DraftSchedule(
            draft_schedule_id="d",
            plan_version="p",
            entries=(_entry(),),
            created_at=datetime(2026, 5, 4, 17, 55),  # naive
        )


def test_draft_is_frozen() -> None:
    draft = _draft()
    with pytest.raises(ValidationError):
        draft.draft_schedule_id = "other"  # type: ignore[misc]


def test_draft_extra_field_rejected() -> None:
    with pytest.raises(ValidationError):
        DraftSchedule.model_validate(
            {
                "draft_schedule_id": "d",
                "plan_version": "p",
                "entries": [
                    {
                        "task_id": "t",
                        "start": "2026-05-04T18:00:00+00:00",
                        "end": "2026-05-04T19:00:00+00:00",
                        "calendar_event_status": "draft_only",
                    }
                ],
                "created_at": "2026-05-04T17:55:00+00:00",
                "extra": "nope",
            }
        )


def test_draft_entries_preserve_order() -> None:
    early = _entry(
        task_id="early",
        start=datetime(2026, 5, 4, 8, 0, tzinfo=UTC),
        end=datetime(2026, 5, 4, 9, 0, tzinfo=UTC),
    )
    late = _entry(
        task_id="late",
        start=datetime(2026, 5, 4, 18, 0, tzinfo=UTC),
        end=datetime(2026, 5, 4, 19, 0, tzinfo=UTC),
    )
    # Pass in non-chronological order; tuple preserves insertion order.
    draft = _draft(entries=(late, early))
    assert [e.task_id for e in draft.entries] == ["late", "early"]


# --------------------------------------------------------------------------- #
# from_scheduler_output
# --------------------------------------------------------------------------- #


def _sched_output(
    status: ScheduleStatus = ScheduleStatus.SUCCESS,
    scheduled: list[ScheduledTask] | None = None,
    unscheduled: list[UnscheduledTask] | None = None,
    repair_options: list[RepairOption] | None = None,
) -> SchedulerOutput:
    return SchedulerOutput(
        run_id="run_xyz",
        plan_version="plan_xyz",
        schedule_status=status,
        scheduled_tasks=scheduled
        if scheduled is not None
        else [
            ScheduledTask(
                task_id="dp_001",
                start=datetime(2026, 5, 4, 18, 0, tzinfo=UTC),
                end=datetime(2026, 5, 4, 19, 0, tzinfo=UTC),
            )
        ],
        unscheduled_tasks=unscheduled or [],
        available_capacity_min=120,
        largest_available_block_min=60,
        repair_options=repair_options or [],
    )


def test_from_scheduler_output_success() -> None:
    out = _sched_output()
    draft = DraftSchedule.from_scheduler_output(
        out,
        draft_schedule_id="draft_xyz",
        created_at=datetime(2026, 5, 4, 17, 55, tzinfo=UTC),
    )
    assert draft.draft_schedule_id == "draft_xyz"
    assert draft.plan_version == "plan_xyz"
    assert len(draft.entries) == 1
    assert draft.entries[0].task_id == "dp_001"
    assert draft.entries[0].calendar_event_status is CalendarEventStatus.DRAFT_ONLY


def test_from_scheduler_output_failed_rejected() -> None:
    out = _sched_output(
        status=ScheduleStatus.FAILED,
        scheduled=[],
        unscheduled=[
            UnscheduledTask(
                task_id="x",
                reason_code=ReasonCode.NO_VALID_CONTIGUOUS_BLOCK,
                debug={"why": "no room"},
            )
        ],
        repair_options=[RepairOption.ASK_USER],
    )
    with pytest.raises(ValueError, match="failed scheduler output"):
        DraftSchedule.from_scheduler_output(
            out,
            draft_schedule_id="d",
            created_at=datetime(2026, 5, 4, 17, 55, tzinfo=UTC),
        )


def test_from_scheduler_output_partial_failure_allowed() -> None:
    out = _sched_output(
        status=ScheduleStatus.PARTIAL_FAILURE,
        unscheduled=[
            UnscheduledTask(
                task_id="bad",
                reason_code=ReasonCode.NO_VALID_CONTIGUOUS_BLOCK,
                debug={"why": "no room"},
            )
        ],
        repair_options=[RepairOption.ASK_USER],
    )
    draft = DraftSchedule.from_scheduler_output(
        out,
        draft_schedule_id="d",
        created_at=datetime(2026, 5, 4, 17, 55, tzinfo=UTC),
    )
    # Only the scheduled tasks appear in the draft.
    assert {e.task_id for e in draft.entries} == {"dp_001"}


def test_from_scheduler_output_preserves_scheduled_order() -> None:
    a = ScheduledTask(
        task_id="a",
        start=datetime(2026, 5, 4, 8, 0, tzinfo=UTC),
        end=datetime(2026, 5, 4, 9, 0, tzinfo=UTC),
    )
    b = ScheduledTask(
        task_id="b",
        start=datetime(2026, 5, 4, 18, 0, tzinfo=UTC),
        end=datetime(2026, 5, 4, 19, 0, tzinfo=UTC),
    )
    out = _sched_output(scheduled=[b, a])  # NB: b before a
    draft = DraftSchedule.from_scheduler_output(
        out,
        draft_schedule_id="d",
        created_at=datetime(2026, 5, 4, 17, 55, tzinfo=UTC),
    )
    assert [e.task_id for e in draft.entries] == ["b", "a"]


# --------------------------------------------------------------------------- #
# with_adjustments
# --------------------------------------------------------------------------- #


def _two_entry_draft() -> DraftSchedule:
    early = _entry(
        task_id="a",
        start=datetime(2026, 5, 4, 8, 0, tzinfo=UTC),
        end=datetime(2026, 5, 4, 9, 0, tzinfo=UTC),  # 60m
    )
    late = _entry(
        task_id="b",
        start=datetime(2026, 5, 4, 18, 0, tzinfo=UTC),
        end=datetime(2026, 5, 4, 20, 0, tzinfo=UTC),  # 120m
    )
    return _draft(entries=(early, late))


def test_with_adjustments_moves_preserving_duration_order_and_plan() -> None:
    draft = _two_entry_draft()
    # Move "b" two days later and to the morning (a cross-day move).
    moved = draft.with_adjustments(
        {"b": datetime(2026, 5, 6, 10, 0, tzinfo=UTC)},
        draft_schedule_id="draft_002",
        created_at=datetime(2026, 5, 4, 17, 55, tzinfo=UTC),
    )
    assert moved.draft_schedule_id == "draft_002"
    assert moved.plan_version == draft.plan_version  # repositioning never re-plans
    # Order preserved: "a" then "b", even though "b" now starts later in the day.
    assert [e.task_id for e in moved.entries] == ["a", "b"]
    assert moved.entries[0] == draft.entries[0]  # untouched task unchanged
    b = moved.entries[1]
    assert b.start == datetime(2026, 5, 6, 10, 0, tzinfo=UTC)
    assert b.end == datetime(2026, 5, 6, 12, 0, tzinfo=UTC)  # 120m preserved, new day
    # The original draft is untouched (immutable).
    assert draft.entries[1].start == datetime(2026, 5, 4, 18, 0, tzinfo=UTC)


def test_with_adjustments_unknown_task_id_rejected() -> None:
    draft = _two_entry_draft()
    with pytest.raises(ValueError, match="unknown task_id"):
        draft.with_adjustments(
            {"nope": datetime(2026, 5, 4, 10, 0, tzinfo=UTC)},
            draft_schedule_id="draft_002",
            created_at=datetime(2026, 5, 4, 17, 55, tzinfo=UTC),
        )


def test_with_adjustments_naive_start_rejected() -> None:
    draft = _two_entry_draft()
    with pytest.raises(ValidationError, match="timezone-aware"):
        draft.with_adjustments(
            {"a": datetime(2026, 5, 4, 10, 0)},  # naive
            draft_schedule_id="draft_002",
            created_at=datetime(2026, 5, 4, 17, 55, tzinfo=UTC),
        )
