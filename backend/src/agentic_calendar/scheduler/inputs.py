"""Input contract for the Scheduler.

The Scheduler accepts a single ``SchedulerInput`` to keep its public API
minimal and to make tests trivial to set up. All fields are immutable.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from agentic_calendar.contracts.task_plan import TaskPlan

from .policy import SchedulingPolicy


class FreeBusyInterval(BaseModel):
    """A single busy interval on the user's calendar (timezone-aware)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    start: datetime
    end: datetime

    @model_validator(mode="after")
    def _aware_and_ordered(self) -> FreeBusyInterval:
        if self.start.tzinfo is None or self.end.tzinfo is None:
            raise ValueError("free/busy intervals must be timezone-aware")
        if self.end <= self.start:
            raise ValueError("free/busy interval end must be after start")
        return self


class SchedulerInput(BaseModel):
    """Everything the Scheduler needs in one frozen object."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str = Field(min_length=1)
    plan_version: str = Field(min_length=1)
    plan: TaskPlan
    policy: SchedulingPolicy
    calendar_free_busy: list[FreeBusyInterval] = Field(default_factory=list)
    completed_task_ids: list[str] = Field(default_factory=list)
    horizon_start: datetime
    horizon_end: datetime

    @model_validator(mode="after")
    def _horizon_aware_and_ordered(self) -> SchedulerInput:
        if self.horizon_start.tzinfo is None or self.horizon_end.tzinfo is None:
            raise ValueError("horizon_start and horizon_end must be timezone-aware")
        if self.horizon_end <= self.horizon_start:
            raise ValueError("horizon_end must be strictly after horizon_start")
        return self
