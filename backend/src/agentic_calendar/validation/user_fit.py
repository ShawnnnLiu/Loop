"""User-fit checks (axiom 04).

* total weekly load <= ``user.weekly_hours * 1.2``;
* no task exceeds ``user.max_session_length_min`` unless ``splittable`` is true;
* tasks are not notably shorter than ``user.preferred_session_length_min``
  (fragmentation signal);
* ``cognitive_load`` is in the allowed range (already enforced by the
  contract; we re-report here so callers get a typed ``Violation`` even when
  the input was assembled programmatically).

The capacity multiplier and preferred-session tolerance are heuristic priors
from the spec; they live here so they can be tuned per phase without touching
the orchestrator.

TODO(phase 4+): high-cognitive-load distribution and beginner-overload
checks (``HIGH_LOAD_TASKS_NOT_DISTRIBUTED`` etc.) are deferred until a
deterministic policy exists. Reasoning:

* ``cognitive_load`` is an LLM-proposed integer in ``[1, 5]`` produced by
  ``PlannerNode``; the Pydantic contract bounds the range but the value
  itself is not calibrated. Per-user calibration lands with Phase 4
  telemetry (axiom 17). Treating raw load as ground truth for "high" before
  calibration would penalise plans whose author happened to be conservative.
* "Distributed across the plan" needs an ordering axis (topological order,
  scheduler placement order, or week-by-week binning). None of those is
  established at the validation layer in Phase 1; scheduler-side ordering
  arrives downstream.
* "Beginner not overloaded early" depends on the same ordering plus a
  deterministic threshold the spec does not pin.

Implementing any of these without the underlying policy would be
heuristic-on-heuristic and likely to fight calibration once it arrives.
"""

from __future__ import annotations

from agentic_calendar.contracts.task_plan import TaskPlan
from agentic_calendar.contracts.user_profile import UserProfile
from agentic_calendar.contracts.validation_result import Violation
from agentic_calendar.contracts.violation_types import ViolationType

from .base import make_violation

WEEKLY_LOAD_TOLERANCE = 1.2
"""Heuristic prior (axiom 04): plan may exceed weekly capacity by up to 20%."""

PREFERRED_SESSION_TOLERANCE_RATIO = 0.5
"""Heuristic prior: a task is "far from preferred" if its duration is below
``preferred_session_length_min * (1 - PREFERRED_SESSION_TOLERANCE_RATIO)``.
The upper-bound case is already caught by ``DURATION_EXCEEDS_USER_MAX_SESSION``
(hard) or by ``splittable=True`` (the scheduler will chunk it), so this check
only flags fragmentation downward."""


def check_user_fit(plan: TaskPlan, user_profile: UserProfile) -> list[Violation]:
    violations: list[Violation] = []
    violations.extend(_session_length_violations(plan, user_profile))
    violations.extend(_preferred_session_length_violations(plan, user_profile))
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


def _preferred_session_length_violations(
    plan: TaskPlan, user: UserProfile
) -> list[Violation]:
    """Flag tasks notably shorter than the user's preferred session length.

    A short task is a fragmentation signal: switching focus into and out of a
    15-minute slot when the user prefers 60-minute sessions wastes ramp-up
    time. The upper-bound case is intentionally not flagged here:

    * tasks above ``max_session_length_min`` with ``splittable=False`` are
      already reported by ``DURATION_EXCEEDS_USER_MAX_SESSION``;
    * splittable long tasks are expected to be chunked by the scheduler.
    """
    out: list[Violation] = []
    lower = int(
        user.preferred_session_length_min * (1 - PREFERRED_SESSION_TOLERANCE_RATIO)
    )
    for t in plan.tasks:
        if t.estimated_duration_min < lower:
            out.append(
                make_violation(
                    ViolationType.DURATION_FAR_FROM_PREFERRED,
                    task_id=t.task_id,
                    duration_min=t.estimated_duration_min,
                    preferred_session_length_min=user.preferred_session_length_min,
                    tolerance_ratio=PREFERRED_SESSION_TOLERANCE_RATIO,
                    lower_bound_min=lower,
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
