"""Re-validation of a hand-adjusted draft (drag-to-adjust).

When the user repositions proposed blocks in the schedule-review UI, the
backend must re-validate the resulting placement *server-side* — the UI's own
conflict checking is advisory and never trusted. This module owns that pure
check plus the typed adjustment request item.

It enforces the hard safety + correctness rules a manual move must still
satisfy (overlap, allowed hours/weekend, daily load) and leaves the soft
placement the scheduler optimizes for (deep-work windows, min break between
deep blocks) deliberately relaxed. Prerequisite ordering is **advisory** for a
manual override — completion-relative and non-blocking (``DEPENDENCY_ADVISORY``,
ADR-0008), never a refusal — because a manual move is an explicit override of
placement. Field semantics follow ``docs/specs/draft-schedule.schema.md`` and
axiom 05.
"""

from __future__ import annotations

from collections.abc import Collection, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, tzinfo

from pydantic import BaseModel, ConfigDict, Field, model_validator

from agentic_calendar.contracts.draft_schedule import DraftScheduleEntry
from agentic_calendar.contracts.reason_codes import ReasonCode
from agentic_calendar.contracts.task_plan import TaskPlan

from .inputs import FreeBusyInterval
from .policy import SchedulingPolicy
from .windows import WEEKDAY_TO_DAY, WEEKEND


class DraftAdjustment(BaseModel):
    """One user-requested move of a proposed block to a new start instant.

    The new ``end`` is derived from the block's original duration, so this
    request carries no ``end`` — a move changes *when* a block runs, never its
    length. A cross-day move is just a different date on ``start``.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    task_id: str = Field(min_length=1)
    start: datetime

    @model_validator(mode="after")
    def _start_tz_aware(self) -> DraftAdjustment:
        if self.start.tzinfo is None:
            raise ValueError("adjustment start must be timezone-aware")
        return self


@dataclass(frozen=True, slots=True)
class PlacementConflict:
    """One reason a hand-adjusted placement was refused (a hard rule)."""

    task_id: str
    reason_code: ReasonCode
    detail: str


@dataclass(frozen=True, slots=True)
class PlacementWarning:
    """One non-blocking advisory on a hand-adjusted placement (ADR-0008).

    The move is applied; the warning is surfaced. Today the only warning is
    ``DEPENDENCY_ADVISORY`` — a manual move that starts before an *unfinished*
    prerequisite ends.
    """

    task_id: str
    reason_code: ReasonCode
    detail: str


@dataclass(frozen=True, slots=True)
class PlacementReview:
    """Outcome of re-validating a hand-adjusted placement (ADR-0008).

    ``conflicts`` are hard-rule violations that refuse the move; ``warnings`` are
    non-blocking advisories surfaced but not blocking. An empty ``conflicts``
    means the move is applied (possibly carrying warnings).
    """

    conflicts: list[PlacementConflict]
    warnings: list[PlacementWarning]


def _to_time(hhmm: str) -> time:
    hour, minute = hhmm.split(":")
    return time(int(hour), int(minute))


def validate_placements(
    entries: Sequence[DraftScheduleEntry],
    *,
    plan: TaskPlan,
    policy: SchedulingPolicy,
    free_busy: Sequence[FreeBusyInterval],
    tz: tzinfo,
    completed_or_dropped_task_ids: Collection[str] = (),
) -> PlacementReview:
    """Re-validate a hand-adjusted set of placements (ADR-0008).

    Returns a :class:`PlacementReview` splitting **hard conflicts** (which refuse
    the move) from **non-blocking warnings** (surfaced, never blocking).

    Hard rules — each a typed ``reason_code`` conflict:

    * no overlap with a fixed external event or another proposed block
      (``NO_VALID_CONTIGUOUS_BLOCK``);
    * within ``[no_events_before, no_events_after]`` and not on a disabled
      weekend (``OUTSIDE_ALLOWED_HOURS``);
    * a calendar day's total stays under ``max_daily_study_min``
      (``DAILY_LOAD_EXCEEDED``).

    Advisory rule — a non-blocking warning, completion-relative:

    * a task that starts before an **unfinished** prerequisite ends warns with
      ``DEPENDENCY_ADVISORY``; a prerequisite in ``completed_or_dropped_task_ids``
      never warns. The deterministic auto-placement scheduler keeps the hard
      ``DEPENDENCY_BLOCKED`` rule — a manual override does not.

    Overlap and prerequisite checks are instant-based (timezone-independent);
    the hour, weekday, and daily-load checks read each entry in the user's local
    timezone ``tz``. Soft placement (deep-work windows, min break between deep
    blocks) is intentionally not re-checked.
    """
    conflicts: list[PlacementConflict] = []
    warnings: list[PlacementWarning] = []
    seen_conflicts: set[tuple[str, ReasonCode]] = set()
    seen_warnings: set[tuple[str, ReasonCode]] = set()

    def add(task_id: str, code: ReasonCode, detail: str) -> None:
        key = (task_id, code)
        if key not in seen_conflicts:
            seen_conflicts.add(key)
            conflicts.append(PlacementConflict(task_id, code, detail))

    def warn(task_id: str, code: ReasonCode, detail: str) -> None:
        key = (task_id, code)
        if key not in seen_warnings:
            seen_warnings.add(key)
            warnings.append(PlacementWarning(task_id, code, detail))

    before = _to_time(policy.no_events_before)
    after = _to_time(policy.no_events_after)
    local = {e.task_id: (e.start.astimezone(tz), e.end.astimezone(tz)) for e in entries}

    # 1. allowed hours + allowed weekday (local wall clock)
    for entry in entries:
        local_start, local_end = local[entry.task_id]
        day = WEEKDAY_TO_DAY[local_start.weekday()]
        if day in WEEKEND and not policy.allow_weekends:
            add(
                entry.task_id,
                ReasonCode.OUTSIDE_ALLOWED_HOURS,
                f"{entry.task_id} placed on {day.value}, but weekends are disabled",
            )
        elif (
            local_start.time() < before
            or local_end.date() != local_start.date()
            or local_end.time() > after
        ):
            add(
                entry.task_id,
                ReasonCode.OUTSIDE_ALLOWED_HOURS,
                f"{entry.task_id} runs outside the allowed "
                f"{policy.no_events_before}-{policy.no_events_after} window",
            )

    # 2. overlap with a fixed external event
    for entry in entries:
        if any(entry.start < busy.end and busy.start < entry.end for busy in free_busy):
            add(
                entry.task_id,
                ReasonCode.NO_VALID_CONTIGUOUS_BLOCK,
                f"{entry.task_id} overlaps a fixed calendar event",
            )

    # 3. overlap between proposed blocks (sorted: later starts can't overlap once clear)
    ordered = sorted(entries, key=lambda e: e.start)
    for index, earlier in enumerate(ordered):
        for later in ordered[index + 1 :]:
            if later.start >= earlier.end:
                break
            add(
                later.task_id,
                ReasonCode.NO_VALID_CONTIGUOUS_BLOCK,
                f"{later.task_id} overlaps {earlier.task_id}",
            )

    # 4. daily-load cap (local calendar day)
    minutes_by_day: dict[date, int] = {}
    first_of_day: dict[date, str] = {}
    for entry in ordered:
        local_start, local_end = local[entry.task_id]
        day_key = local_start.date()
        minutes_by_day[day_key] = minutes_by_day.get(day_key, 0) + int(
            (local_end - local_start).total_seconds() // 60
        )
        first_of_day.setdefault(day_key, entry.task_id)
    for day_key, total in minutes_by_day.items():
        if total > policy.max_daily_study_min:
            add(
                first_of_day[day_key],
                ReasonCode.DAILY_LOAD_EXCEEDED,
                f"{day_key.isoformat()} totals {total}m, over the "
                f"{policy.max_daily_study_min}m daily cap",
            )

    # 5. prerequisite order — advisory + completion-relative (ADR-0008). A manual
    #    override past an *unfinished* prerequisite warns (non-blocking); a
    #    completed/dropped prerequisite is skipped. Auto-placement keeps the hard
    #    DEPENDENCY_BLOCKED rule (the greedy scheduler), not this path.
    done = set(completed_or_dropped_task_ids)
    end_by_task = {entry.task_id: entry.end for entry in entries}
    deps_by_task = {task.task_id: task.dependencies for task in plan.tasks}
    for entry in entries:
        for dependency in deps_by_task.get(entry.task_id, ()):
            if dependency in done:
                continue
            dependency_end = end_by_task.get(dependency)
            if dependency_end is not None and entry.start < dependency_end:
                warn(
                    entry.task_id,
                    ReasonCode.DEPENDENCY_ADVISORY,
                    f"{entry.task_id} starts before unfinished prerequisite "
                    f"{dependency} ends",
                )
                break

    return PlacementReview(conflicts=conflicts, warnings=warnings)
