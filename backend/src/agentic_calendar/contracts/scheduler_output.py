"""``scheduler_output`` contract.

Canonical spec: ``docs/specs/scheduler-output.schema.md``.

The Scheduler always returns one of these. Hard rules:

* ``unscheduled_tasks[*]`` must have a typed ``reason_code`` and a
  ``debug`` payload (axiom 05).
* ``scheduled_tasks[*]`` must NOT carry ``calendar_event_id`` — the
  Scheduler does not write to the calendar (axiom 05 / 06).
* ``schedule_status="success"`` ⇒ no unscheduled tasks; ``"failed"`` ⇒
  no scheduled tasks; ``"partial_failure"`` ⇒ both lists non-empty.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .reason_codes import ReasonCode


class ScheduleStatus(StrEnum):
    SUCCESS = "success"
    PARTIAL_FAILURE = "partial_failure"
    FAILED = "failed"


class CalendarEventStatus(StrEnum):
    """Phase 1 only ever produces ``DRAFT_ONLY``."""

    DRAFT_ONLY = "draft_only"


class RepairOption(StrEnum):
    """Deterministic repair options the Scheduler may suggest."""

    SPLIT_LARGE_TASKS = "split_large_tasks"
    SPLIT_TASK = "split_task"
    EXTEND_TIMELINE = "extend_timeline"
    REDUCE_SCOPE = "reduce_scope"
    INCREASE_WEEKLY_HOURS = "increase_weekly_hours"
    RELAX_ALLOWED_HOURS = "relax_allowed_hours"
    ASK_USER = "ask_user"


class ScheduledTask(BaseModel):
    """One placement of a task in calendar time (draft only)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    task_id: str = Field(min_length=1)
    start: datetime
    end: datetime
    calendar_event_status: CalendarEventStatus = CalendarEventStatus.DRAFT_ONLY

    @model_validator(mode="after")
    def _times_make_sense(self) -> ScheduledTask:
        if self.start.tzinfo is None or self.end.tzinfo is None:
            raise ValueError("scheduled task start/end must be timezone-aware")
        if self.end <= self.start:
            raise ValueError("scheduled task end must be strictly after start")
        return self


class UnscheduledTask(BaseModel):
    """A task the Scheduler could not place, with typed reason + debug."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    task_id: str = Field(min_length=1)
    reason_code: ReasonCode
    debug: dict[str, Any] = Field(min_length=1)


class SchedulerOutput(BaseModel):
    """Always-a-draft Scheduler output (see ``scheduler-output.schema.md``)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str = Field(min_length=1)
    plan_version: str = Field(min_length=1)
    schedule_status: ScheduleStatus
    scheduled_tasks: list[ScheduledTask] = Field(default_factory=list)
    unscheduled_tasks: list[UnscheduledTask] = Field(default_factory=list)
    available_capacity_min: int = Field(ge=0)
    largest_available_block_min: int = Field(ge=0)
    repair_options: list[RepairOption] = Field(default_factory=list)

    @model_validator(mode="after")
    def _status_matches_lists(self) -> SchedulerOutput:
        match self.schedule_status:
            case ScheduleStatus.SUCCESS:
                if self.unscheduled_tasks:
                    raise ValueError(
                        "schedule_status='success' must have empty unscheduled_tasks"
                    )
            case ScheduleStatus.FAILED:
                if self.scheduled_tasks:
                    raise ValueError(
                        "schedule_status='failed' must have empty scheduled_tasks"
                    )
                if not self.unscheduled_tasks:
                    raise ValueError(
                        "schedule_status='failed' must have at least one unscheduled task"
                    )
            case ScheduleStatus.PARTIAL_FAILURE:
                if not self.scheduled_tasks or not self.unscheduled_tasks:
                    raise ValueError(
                        "schedule_status='partial_failure' requires non-empty "
                        "scheduled_tasks and unscheduled_tasks"
                    )
        return self

    @model_validator(mode="after")
    def _repair_options_required_when_not_success(self) -> SchedulerOutput:
        if (
            self.schedule_status is not ScheduleStatus.SUCCESS
            and not self.repair_options
        ):
            raise ValueError(
                "repair_options must be non-empty unless schedule_status='success'"
            )
        return self

    @model_validator(mode="after")
    def _scheduled_task_ids_unique(self) -> SchedulerOutput:
        seen: set[str] = set()
        for st in self.scheduled_tasks:
            if st.task_id in seen:
                raise ValueError(
                    f"task_id {st.task_id!r} appears more than once in scheduled_tasks"
                )
            seen.add(st.task_id)
        return self
