"""User-fit checks (axiom 04).

* total weekly load <= ``user.weekly_hours * 1.2``;
* no task exceeds ``user.max_session_length_min`` unless ``splittable`` is true;
* ``cognitive_load`` is in the allowed range (already enforced by the
  contract; we re-report here so callers get a typed ``Violation`` even when
  the input was assembled programmatically).

The 1.2 capacity multiplier is the heuristic prior from the spec; it lives
here so it can be tuned per phase without touching the orchestrator.
"""

from __future__ import annotations

from agentic_calendar.contracts.task_plan import TaskPlan
from agentic_calendar.contracts.user_profile import UserProfile
from agentic_calendar.contracts.validation_result import Violation
from agentic_calendar.contracts.violation_types import ViolationType

from .base import make_violation

WEEKLY_LOAD_TOLERANCE = 1.2
"""Heuristic prior (axiom 04): plan may exceed weekly capacity by up to 20%."""


def check_user_fit(plan: TaskPlan, user_profile: UserProfile) -> list[Violation]:
    violations: list[Violation] = []
    violations.extend(_session_length_violations(plan, user_profile))
    violations.extend(_weekly_load_violation(plan, user_profile))
    violations.extend(_cognitive_load_violations(plan))
    return violations


def _session_length_violations(
    plan: TaskPlan, user: UserProfile
) -> list[Violation]:
    out: list[Violation] = []
    for t in plan.tasks:
        if (
            t.estimated_duration_min > user.max_session_length_min
            and not t.splittable
        ):
            out.append(
                make_violation(
                    ViolationType.DURATION_EXCEEDS_USER_MAX_SESSION,
                    task_id=t.task_id,
                    duration_min=t.estimated_duration_min,
                    max_session_length_min=user.max_session_length_min,
                    splittable=t.splittable,
                )
            )
    return out


def _weekly_load_violation(plan: TaskPlan, user: UserProfile) -> list[Violation]:
    """Total plan minutes must fit roughly within (timeline_weeks * weekly_hours)."""
    total_min = sum(t.estimated_duration_min for t in plan.tasks)
    capacity_min = int(user.weekly_hours * 60 * user.timeline_weeks)
    cap_with_tolerance = int(capacity_min * WEEKLY_LOAD_TOLERANCE)
    if total_min <= cap_with_tolerance:
        return []
    return [
        make_violation(
            ViolationType.WEEKLY_LOAD_EXCEEDS_CAPACITY,
            total_plan_min=total_min,
            capacity_min=capacity_min,
            tolerance=WEEKLY_LOAD_TOLERANCE,
            cap_with_tolerance_min=cap_with_tolerance,
            timeline_weeks=user.timeline_weeks,
            weekly_hours=user.weekly_hours,
        )
    ]


def _cognitive_load_violations(plan: TaskPlan) -> list[Violation]:
    """Re-report cognitive_load out-of-range as a typed violation.

    The Pydantic contract already enforces the 1..5 range, so this only fires
    when the input was constructed programmatically (e.g. test harnesses).
    """
    out: list[Violation] = []
    for t in plan.tasks:
        if t.cognitive_load < 1 or t.cognitive_load > 5:
            out.append(
                make_violation(
                    ViolationType.COGNITIVE_LOAD_OUT_OF_RANGE,
                    task_id=t.task_id,
                    cognitive_load=t.cognitive_load,
                )
            )
    return out
