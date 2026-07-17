"""Scheduling policy derived from a ``user_profile``.

The Scheduler accepts a ``SchedulingPolicy`` directly; this helper builds the
default policy from a profile so callers do not have to repeat the mapping.
Field semantics follow ``docs/specs/scheduler-output.schema.md``.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from agentic_calendar.contracts.common_types import HHMM, Day
from agentic_calendar.contracts.user_profile import UserProfile


class DeepWorkWindowPolicy(BaseModel):
    """Recurring weekly deep-work window in the user's local timezone."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    day: Day
    start: HHMM
    end: HHMM


class SchedulingPolicy(BaseModel):
    """Pure-data scheduling policy passed to the Scheduler.

    Note: there is no separate ``max_contiguous_study_min``; the scheduler
    uses ``max_session_length_min`` as the per-task cap. Re-introducing a
    distinct contiguous-study cap requires an axiom-05 update first.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    no_events_before: HHMM
    no_events_after: HHMM
    allow_weekends: bool = True
    min_break_between_deep_blocks_min: int = Field(ge=0, le=12 * 60)
    max_daily_study_min: int = Field(gt=0, le=24 * 60)
    respect_deep_work_windows: bool = True
    deep_work_windows: list[DeepWorkWindowPolicy] = Field(default_factory=list)
    max_session_length_min: int = Field(gt=0, le=12 * 60)
    preferred_session_length_min: int = Field(gt=0, le=12 * 60)
    prefer_evening_sessions: bool = False
    prefer_weekend_long_blocks: bool = False
    avoid_back_to_back_deep_work: bool = False


def policy_from_user_profile(user: UserProfile) -> SchedulingPolicy:
    """Derive a default ``SchedulingPolicy`` from a ``UserProfile``."""
    return SchedulingPolicy(
        no_events_before=user.hard_constraints.no_events_before,
        no_events_after=user.hard_constraints.no_events_after,
        allow_weekends=user.hard_constraints.allow_weekends,
        min_break_between_deep_blocks_min=(
            user.hard_constraints.min_break_between_deep_blocks_min
        ),
        max_daily_study_min=user.hard_constraints.max_daily_study_min,
        respect_deep_work_windows=True,
        deep_work_windows=[
            DeepWorkWindowPolicy(day=w.day, start=w.start, end=w.end)
            for w in user.deep_work_windows
        ],
        max_session_length_min=user.max_session_length_min,
        preferred_session_length_min=user.preferred_session_length_min,
        prefer_evening_sessions=user.preferences.prefer_evening_sessions,
        prefer_weekend_long_blocks=user.preferences.prefer_weekend_long_blocks,
        avoid_back_to_back_deep_work=user.preferences.avoid_back_to_back_deep_work,
    )
