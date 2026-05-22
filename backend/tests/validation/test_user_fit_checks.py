"""Tests for ``validation.user_fit.check_user_fit``."""

from __future__ import annotations

from agentic_calendar.contracts.violation_types import ViolationType
from agentic_calendar.validation.user_fit import (
    PREFERRED_SESSION_TOLERANCE_RATIO,
    WEEKLY_LOAD_TOLERANCE,
    check_user_fit,
)
from tests.validation._helpers import load_user_profile, make_plan, make_task


def test_within_capacity_no_violations() -> None:
    user = load_user_profile()
    plan = make_plan(
        make_task(task_id="t1", estimated_duration_min=60),
        make_task(task_id="t2", estimated_duration_min=60),
    )
    assert check_user_fit(plan, user) == []


def test_unsplittable_long_task_rejected() -> None:
    user = load_user_profile()  # max_session_length_min == 120
    plan = make_plan(
        make_task(
            task_id="long",
            estimated_duration_min=180,
            splittable=False,
        )
    )
    violations = check_user_fit(plan, user)
    assert any(
        v.type is ViolationType.DURATION_EXCEEDS_USER_MAX_SESSION
        for v in violations
    )


def test_splittable_long_task_allowed() -> None:
    user = load_user_profile()
    plan = make_plan(
        make_task(
            task_id="long",
            estimated_duration_min=180,
            splittable=True,
        )
    )
    violations = check_user_fit(plan, user)
    assert all(
        v.type is not ViolationType.DURATION_EXCEEDS_USER_MAX_SESSION
        for v in violations
    )


def test_weekly_load_overflow_rejected() -> None:
    user = load_user_profile()  # weekly_hours=8, timeline_weeks=10 → 4800 min cap
    cap = int(user.weekly_hours * 60 * user.timeline_weeks * WEEKLY_LOAD_TOLERANCE)
    too_many = (cap // 60) + 5  # tasks of 60 min each → exceed cap
    plan = make_plan(
        *[
            make_task(task_id=f"t_{i}", estimated_duration_min=60)
            for i in range(too_many)
        ]
    )
    violations = check_user_fit(plan, user)
    matching = [
        v for v in violations if v.type is ViolationType.WEEKLY_LOAD_EXCEEDS_CAPACITY
    ]
    assert len(matching) == 1
    details = matching[0].details
    assert details["total_plan_min"] >= details["cap_with_tolerance_min"]


def test_weekly_load_within_tolerance_allowed() -> None:
    user = load_user_profile()
    cap = int(user.weekly_hours * 60 * user.timeline_weeks * WEEKLY_LOAD_TOLERANCE)
    just_under = cap - 60
    plan = make_plan(
        *[
            make_task(task_id=f"t_{i}", estimated_duration_min=60)
            for i in range(just_under // 60)
        ]
    )
    violations = check_user_fit(plan, user)
    assert not any(
        v.type is ViolationType.WEEKLY_LOAD_EXCEEDS_CAPACITY for v in violations
    )


def test_task_far_below_preferred_flagged() -> None:
    """A 15-min task when preferred is 60 min should fire DURATION_FAR_FROM_PREFERRED."""
    user = load_user_profile()  # preferred_session_length_min = 60
    lower = int(user.preferred_session_length_min * (1 - PREFERRED_SESSION_TOLERANCE_RATIO))
    too_short = lower - 1  # one minute below the soft floor
    plan = make_plan(make_task(task_id="t1", estimated_duration_min=too_short))
    violations = check_user_fit(plan, user)
    matching = [
        v for v in violations if v.type is ViolationType.DURATION_FAR_FROM_PREFERRED
    ]
    assert len(matching) == 1
    v = matching[0]
    assert v.task_id == "t1"
    assert v.details["duration_min"] == too_short
    assert v.details["preferred_session_length_min"] == user.preferred_session_length_min
    assert v.details["lower_bound_min"] == lower
    assert v.details["tolerance_ratio"] == PREFERRED_SESSION_TOLERANCE_RATIO


def test_task_at_lower_bound_allowed() -> None:
    """A task exactly at the tolerance floor must not fire."""
    user = load_user_profile()
    lower = int(user.preferred_session_length_min * (1 - PREFERRED_SESSION_TOLERANCE_RATIO))
    plan = make_plan(make_task(task_id="t1", estimated_duration_min=lower))
    violations = check_user_fit(plan, user)
    assert not any(
        v.type is ViolationType.DURATION_FAR_FROM_PREFERRED for v in violations
    )


def test_task_above_preferred_not_flagged_by_preferred_check() -> None:
    """The preferred-session check only fires below preferred.

    Above-preferred is already covered by ``DURATION_EXCEEDS_USER_MAX_SESSION``
    (hard) or by ``splittable=True`` (the scheduler chunks it).
    """
    user = load_user_profile()  # preferred=60, max=120
    plan = make_plan(
        make_task(task_id="t1", estimated_duration_min=90, splittable=True),
        make_task(task_id="t2", estimated_duration_min=120, splittable=True),
    )
    violations = check_user_fit(plan, user)
    assert not any(
        v.type is ViolationType.DURATION_FAR_FROM_PREFERRED for v in violations
    )


def test_existing_fixture_durations_pass_preferred_check() -> None:
    """The committed valid task_plan fixture (60-min / 90-min tasks at preferred=60)
    must not regress under the new soft check."""
    user = load_user_profile()
    plan = make_plan(
        make_task(task_id="t1", estimated_duration_min=60),
        make_task(task_id="t2", estimated_duration_min=90),
    )
    violations = check_user_fit(plan, user)
    assert not any(
        v.type is ViolationType.DURATION_FAR_FROM_PREFERRED for v in violations
    )
