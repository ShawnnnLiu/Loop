"""Tests for drag-to-adjust re-validation (``scheduler/adjustment.py``).

``validate_placements`` is the server-side gate that re-checks a hand-moved
draft. These tests pin each typed ``reason_code`` it must emit, prove the
*relaxed* soft placement (deep-work windows) really is relaxed, and prove the
hour/weekday checks read the user's local timezone.
"""

from __future__ import annotations

from collections.abc import Collection
from datetime import UTC, datetime, timedelta, tzinfo
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from agentic_calendar.contracts.common_types import FocusLevel, TaskCategory
from agentic_calendar.contracts.draft_schedule import DraftScheduleEntry
from agentic_calendar.contracts.reason_codes import ReasonCode
from agentic_calendar.contracts.task_plan import Task, TaskPlan
from agentic_calendar.scheduler.adjustment import (
    DraftAdjustment,
    PlacementReview,
    validate_placements,
)
from agentic_calendar.scheduler.inputs import FreeBusyInterval
from agentic_calendar.scheduler.policy import DeepWorkWindowPolicy, SchedulingPolicy

# Monday 2026-05-04 anchors weekday math; Saturday 2026-05-09 is the weekend probe.
MON = datetime(2026, 5, 4, tzinfo=UTC)
SAT = datetime(2026, 5, 9, tzinfo=UTC)


def _policy(**overrides: object) -> SchedulingPolicy:
    base: dict[str, object] = {
        "no_events_before": "08:00",
        "no_events_after": "22:30",
        "allow_weekends": True,
        "min_break_between_deep_blocks_min": 30,
        "max_daily_study_min": 180,
        "respect_deep_work_windows": True,
        "deep_work_windows": [],
        "max_session_length_min": 120,
    }
    base.update(overrides)
    return SchedulingPolicy.model_validate(base)


def _entry(task_id: str, start: datetime, dur_min: int) -> DraftScheduleEntry:
    return DraftScheduleEntry(
        task_id=task_id, start=start, end=start + timedelta(minutes=dur_min)
    )


def _at(day: datetime, hour: int, minute: int = 0) -> datetime:
    return day.replace(hour=hour, minute=minute)


def _plan(deps: dict[str, list[str]]) -> TaskPlan:
    return TaskPlan(
        plan_version="plan_001",
        tasks=[
            Task(
                task_id=task_id,
                module_id="m1",
                title="t",
                dependencies=task_deps,
                estimated_duration_min=60,
                cognitive_load=3,
                category=TaskCategory.PRACTICE,
                required_focus_level=FocusLevel.DEEP,
            )
            for task_id, task_deps in deps.items()
        ],
    )


def _review(
    entries: list[DraftScheduleEntry],
    *,
    plan: TaskPlan | None = None,
    policy: SchedulingPolicy | None = None,
    free_busy: list[FreeBusyInterval] | None = None,
    tz: tzinfo = UTC,
    completed_or_dropped: Collection[str] = (),
) -> PlacementReview:
    return validate_placements(
        entries,
        plan=plan or _plan({e.task_id: [] for e in entries}),
        policy=policy or _policy(),
        free_busy=free_busy or [],
        tz=tz,
        completed_or_dropped_task_ids=completed_or_dropped,
    )


def _validate(
    entries: list[DraftScheduleEntry],
    *,
    plan: TaskPlan | None = None,
    policy: SchedulingPolicy | None = None,
    free_busy: list[FreeBusyInterval] | None = None,
    tz: tzinfo = UTC,
) -> list[ReasonCode]:
    review = _review(entries, plan=plan, policy=policy, free_busy=free_busy, tz=tz)
    return [c.reason_code for c in review.conflicts]


# --------------------------------------------------------------------------- #
# clean pass
# --------------------------------------------------------------------------- #


def test_clean_placement_passes() -> None:
    entries = [
        _entry("a", _at(MON, 9), 60),
        _entry("b", _at(MON, 13), 60),
    ]
    assert _validate(entries) == []


# --------------------------------------------------------------------------- #
# overlaps -> NO_VALID_CONTIGUOUS_BLOCK
# --------------------------------------------------------------------------- #


def test_overlap_with_fixed_event_rejected() -> None:
    entries = [_entry("a", _at(MON, 9), 60)]
    busy = [FreeBusyInterval(start=_at(MON, 9, 30), end=_at(MON, 10, 30))]
    assert _validate(entries, free_busy=busy) == [ReasonCode.NO_VALID_CONTIGUOUS_BLOCK]


def test_overlap_between_blocks_rejected() -> None:
    # 60m each, overlapping, same day — total 120m stays under the daily cap so
    # the only violation is the overlap.
    entries = [
        _entry("a", _at(MON, 9), 60),
        _entry("b", _at(MON, 9, 30), 60),
    ]
    assert _validate(entries) == [ReasonCode.NO_VALID_CONTIGUOUS_BLOCK]


# --------------------------------------------------------------------------- #
# allowed hours / weekday -> OUTSIDE_ALLOWED_HOURS
# --------------------------------------------------------------------------- #


def test_before_allowed_hours_rejected() -> None:
    entries = [_entry("a", _at(MON, 7), 60)]  # 07:00 < 08:00
    assert _validate(entries) == [ReasonCode.OUTSIDE_ALLOWED_HOURS]


def test_after_allowed_hours_rejected() -> None:
    entries = [_entry("a", _at(MON, 22), 60)]  # ends 23:00 > 22:30
    assert _validate(entries) == [ReasonCode.OUTSIDE_ALLOWED_HOURS]


def test_disabled_weekend_rejected() -> None:
    entries = [_entry("a", _at(SAT, 10), 60)]
    assert _validate(entries, policy=_policy(allow_weekends=False)) == [
        ReasonCode.OUTSIDE_ALLOWED_HOURS
    ]


def test_allowed_weekend_passes() -> None:
    entries = [_entry("a", _at(SAT, 10), 60)]
    assert _validate(entries, policy=_policy(allow_weekends=True)) == []


# --------------------------------------------------------------------------- #
# daily load -> DAILY_LOAD_EXCEEDED
# --------------------------------------------------------------------------- #


def test_daily_load_exceeded_rejected() -> None:
    # 120 + 120 = 240 > 180 cap; non-overlapping so the cap is the only fault.
    entries = [
        _entry("a", _at(MON, 9), 120),
        _entry("b", _at(MON, 13), 120),
    ]
    assert _validate(entries) == [ReasonCode.DAILY_LOAD_EXCEEDED]


# --------------------------------------------------------------------------- #
# prerequisite order -> advisory (DEPENDENCY_ADVISORY), completion-relative
# --------------------------------------------------------------------------- #


def test_prerequisite_order_violation_warns_not_blocks() -> None:
    plan = _plan({"dp_001": [], "dp_002": ["dp_001"]})
    # dp_002 placed entirely before its prerequisite dp_001 (no overlap, so the
    # only fault is the ordering) -> advisory warning, NOT a refusal (ADR-0008).
    entries = [
        _entry("dp_001", _at(MON, 18), 60),  # ends 19:00
        _entry("dp_002", _at(MON, 9), 90),  # starts 09:00 < 19:00
    ]
    review = _review(entries, plan=plan)
    assert review.conflicts == []
    assert [w.reason_code for w in review.warnings] == [ReasonCode.DEPENDENCY_ADVISORY]
    assert review.warnings[0].task_id == "dp_002"


def test_prerequisite_order_satisfied_no_warning() -> None:
    plan = _plan({"dp_001": [], "dp_002": ["dp_001"]})
    entries = [
        _entry("dp_001", _at(MON, 18), 60),  # ends 19:00
        _entry("dp_002", _at(MON, 19, 30), 90),  # starts after 19:00
    ]
    review = _review(entries, plan=plan)
    assert review.conflicts == []
    assert review.warnings == []


def test_completed_or_dropped_prerequisite_suppresses_warning() -> None:
    plan = _plan({"dp_001": [], "dp_002": ["dp_001"]})
    entries = [
        _entry("dp_001", _at(MON, 18), 60),
        _entry("dp_002", _at(MON, 9), 90),  # before dp_001, but dp_001 is done
    ]
    review = _review(entries, plan=plan, completed_or_dropped={"dp_001"})
    assert review.conflicts == []
    assert review.warnings == []  # a completed/dropped prerequisite never warns


def test_hard_conflict_and_advisory_coexist() -> None:
    # dp_002 starts before its prerequisite dp_001 (advisory) AND overlaps a
    # fixed event (hard). The hard conflict still blocks; the advisory surfaces.
    plan = _plan({"dp_001": [], "dp_002": ["dp_001"]})
    entries = [
        _entry("dp_001", _at(MON, 18), 60),  # ends 19:00
        _entry("dp_002", _at(MON, 9), 90),  # 09:00-10:30, before dp_001
    ]
    busy = [FreeBusyInterval(start=_at(MON, 9, 30), end=_at(MON, 10, 30))]
    review = _review(entries, plan=plan, free_busy=busy)
    assert [c.reason_code for c in review.conflicts] == [
        ReasonCode.NO_VALID_CONTIGUOUS_BLOCK
    ]
    assert [w.reason_code for w in review.warnings] == [ReasonCode.DEPENDENCY_ADVISORY]


# --------------------------------------------------------------------------- #
# relaxed soft placement: deep-work windows are NOT re-checked
# --------------------------------------------------------------------------- #


def test_deep_work_window_adherence_is_relaxed() -> None:
    # A deep block placed OUTSIDE the configured deep-work window but inside the
    # allowed hours is accepted — manual moves override soft placement.
    policy = _policy(
        deep_work_windows=[DeepWorkWindowPolicy(day="Mon", start="18:00", end="21:00")]
    )
    entries = [_entry("a", _at(MON, 9), 60)]  # 09:00, outside the 18:00-21:00 window
    assert _validate(entries, policy=policy) == []


# --------------------------------------------------------------------------- #
# timezone: hour/weekday checks read the user's local wall clock
# --------------------------------------------------------------------------- #


def test_hours_checked_in_local_timezone() -> None:
    # 11:00Z is 07:00 in New York (UTC-4 in May) — before the 08:00 local bound.
    entries = [_entry("a", datetime(2026, 5, 4, 11, 0, tzinfo=UTC), 60)]
    assert _validate(entries, tz=ZoneInfo("America/New_York")) == [
        ReasonCode.OUTSIDE_ALLOWED_HOURS
    ]
    # 13:00Z is 09:00 New York — inside the window, so it passes.
    ok = [_entry("a", datetime(2026, 5, 4, 13, 0, tzinfo=UTC), 60)]
    assert _validate(ok, tz=ZoneInfo("America/New_York")) == []


# --------------------------------------------------------------------------- #
# DraftAdjustment request item
# --------------------------------------------------------------------------- #


def test_draft_adjustment_requires_tz_aware_start() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        DraftAdjustment(task_id="a", start=datetime(2026, 5, 4, 10, 0))  # naive


def test_draft_adjustment_rejects_extra_field() -> None:
    with pytest.raises(ValidationError):
        DraftAdjustment.model_validate(
            {"task_id": "a", "start": "2026-05-04T10:00:00+00:00", "end": "nope"}
        )
