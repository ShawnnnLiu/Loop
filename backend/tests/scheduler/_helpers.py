"""Shared scheduler-test helpers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from agentic_calendar.contracts.task_plan import TaskPlan
from agentic_calendar.scheduler.inputs import FreeBusyInterval, SchedulerInput
from agentic_calendar.scheduler.policy import (
    DeepWorkWindowPolicy,
    SchedulingPolicy,
)


def make_task(
    *,
    task_id: str = "t1",
    module_id: str = "dp",
    title: str = "task",
    dependencies: list[str] | None = None,
    estimated_duration_min: int = 60,
    cognitive_load: int = 3,
    category: str = "practice",
    required_focus_level: str = "medium",
    splittable: bool = False,
) -> dict[str, Any]:
    return {
        "task_id": task_id,
        "module_id": module_id,
        "title": title,
        "dependencies": list(dependencies or []),
        "estimated_duration_min": estimated_duration_min,
        "cognitive_load": cognitive_load,
        "category": category,
        "required_focus_level": required_focus_level,
        "splittable": splittable,
    }


def make_plan(*tasks: dict[str, Any], plan_version: str = "plan_test") -> TaskPlan:
    return TaskPlan.model_validate(
        {"plan_version": plan_version, "tasks": list(tasks)}
    )


DEFAULT_POLICY = SchedulingPolicy(
    no_events_before="08:00",
    no_events_after="22:30",
    allow_weekends=True,
    max_contiguous_study_min=120,
    min_break_between_deep_blocks_min=30,
    max_daily_study_min=240,
    respect_deep_work_windows=False,
    deep_work_windows=[],
    max_session_length_min=120,
)


DEEP_WORK_POLICY = SchedulingPolicy(
    no_events_before="08:00",
    no_events_after="22:30",
    allow_weekends=True,
    max_contiguous_study_min=120,
    min_break_between_deep_blocks_min=30,
    max_daily_study_min=240,
    respect_deep_work_windows=True,
    deep_work_windows=[
        DeepWorkWindowPolicy(day="Mon", start="18:00", end="21:00"),
        DeepWorkWindowPolicy(day="Tue", start="18:00", end="21:00"),
    ],
    max_session_length_min=120,
)


def make_input(
    plan: TaskPlan,
    *,
    policy: SchedulingPolicy | None = None,
    free_busy: list[FreeBusyInterval] | None = None,
    completed_task_ids: list[str] | None = None,
    horizon_days: int = 3,
    horizon_start: datetime | None = None,
    run_id: str = "run_test",
    plan_version: str | None = None,
) -> SchedulerInput:
    start = horizon_start or datetime(2026, 5, 4, 0, 0, 0, tzinfo=UTC)
    end = start + timedelta(days=horizon_days)
    return SchedulerInput(
        run_id=run_id,
        plan_version=plan_version or plan.plan_version,
        plan=plan,
        policy=policy or DEFAULT_POLICY,
        calendar_free_busy=free_busy or [],
        completed_task_ids=completed_task_ids or [],
        horizon_start=start,
        horizon_end=end,
    )


def busy(start: datetime, *, minutes: int) -> FreeBusyInterval:
    return FreeBusyInterval(start=start, end=start + timedelta(minutes=minutes))
