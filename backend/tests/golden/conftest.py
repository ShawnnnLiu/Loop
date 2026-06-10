"""Shared fixtures for the golden-test scenarios.

Each scenario file imports these fixtures and asserts on:

* the typed ``ReasonCode``,
* the structured debug / repair payload,
* the Supervisor's next state via the deterministic ``route()`` table,
* the no-calendar-write invariant (no ``calendar_event_id`` ever leaks out
  of Phase 1; ``CalendarEventStatus`` is always ``DRAFT_ONLY``),
* validation never mutates the artifact under test.

The fixtures here are intentionally tiny: the goal is to make every
scenario read like its English description in
``docs/golden-test-cases.md``.
"""

from __future__ import annotations

import copy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from agentic_calendar.contracts.scheduler_output import ScheduledTask
from agentic_calendar.contracts.syllabus_units import SyllabusUnits
from agentic_calendar.contracts.task_plan import TaskPlan
from agentic_calendar.contracts.user_profile import UserProfile
from agentic_calendar.scheduler.policy import (
    DeepWorkWindowPolicy,
    SchedulingPolicy,
    policy_from_user_profile,
)
from tests._fixture_loader import iter_valid


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Apply ``@pytest.mark.golden`` to every collected item under ``tests/golden/``.

    Lets the Makefile expose ``make test-fast`` (= ``pytest -m "not golden"``)
    without each scenario file having to repeat the decorator.
    """
    del config
    golden_dir = Path(__file__).resolve().parent
    marker = pytest.mark.golden
    for item in items:
        try:
            item_path = Path(str(item.path))
        except (AttributeError, TypeError):
            continue
        if golden_dir in item_path.parents or item_path == golden_dir:
            item.add_marker(marker)


HORIZON_START = datetime(2026, 5, 4, 0, 0, 0, tzinfo=UTC)
"""Pinned UTC anchor (Mon 2026-05-04). Frozen so deep-work day-of-week math
is deterministic across machines and timezones."""


@pytest.fixture()
def user_profile() -> UserProfile:
    return UserProfile.model_validate(next(iter_valid("user_profile")).payload)


@pytest.fixture()
def syllabus() -> SyllabusUnits:
    return SyllabusUnits.model_validate(next(iter_valid("syllabus_units")).payload)


@pytest.fixture()
def policy(user_profile: UserProfile) -> SchedulingPolicy:
    return policy_from_user_profile(user_profile)


@pytest.fixture()
def relaxed_policy() -> SchedulingPolicy:
    """A wide-open policy used by scenarios that focus on the plan, not the calendar."""
    return SchedulingPolicy(
        no_events_before="08:00",
        no_events_after="22:30",
        allow_weekends=True,
        min_break_between_deep_blocks_min=30,
        max_daily_study_min=240,
        respect_deep_work_windows=False,
        deep_work_windows=[],
        max_session_length_min=120,
    )


@pytest.fixture()
def deep_only_policy() -> SchedulingPolicy:
    """Deep-work windows enforced, used by scheduler-side scenarios."""
    return SchedulingPolicy(
        no_events_before="08:00",
        no_events_after="22:30",
        allow_weekends=True,
        min_break_between_deep_blocks_min=30,
        max_daily_study_min=240,
        respect_deep_work_windows=True,
        deep_work_windows=[
            DeepWorkWindowPolicy(day="Mon", start="18:00", end="21:00"),
            DeepWorkWindowPolicy(day="Tue", start="18:00", end="21:00"),
        ],
        max_session_length_min=120,
    )


def make_task(
    *,
    task_id: str,
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


def assert_no_calendar_write_leaks(scheduler_output: Any) -> None:
    """Phase 1 invariant: nothing the Scheduler emits has been written.

    Per axiom 06, only the Calendar Write Manager (Phase 2) is allowed to
    mint a ``calendar_event_id``. Phase 1 must never expose one — any
    scheduled task is ``DRAFT_ONLY``. The field-level check inspects
    ``model_fields`` (a ``hasattr`` probe on a frozen ``extra="forbid"``
    model is vacuously false and would verify nothing).
    """
    assert "calendar_event_id" not in ScheduledTask.model_fields, (
        "ScheduledTask grew a calendar_event_id field — the Scheduler must "
        "never carry calendar write identifiers (axiom 05/06)"
    )
    for st in scheduler_output.scheduled_tasks:
        assert st.calendar_event_status.value == "draft_only"


def deep_copy_plan(plan: TaskPlan) -> dict[str, Any]:
    """Snapshot a plan as a plain dict so we can detect post-validation mutation."""
    return copy.deepcopy(plan.model_dump())
