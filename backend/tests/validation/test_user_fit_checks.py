"""Tests for ``validation.user_fit.check_user_fit``."""

from __future__ import annotations

from agentic_calendar.contracts.violation_types import ViolationType
from agentic_calendar.validation.user_fit import (
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
