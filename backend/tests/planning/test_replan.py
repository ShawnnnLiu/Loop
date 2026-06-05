"""Tests for the deterministic duration-drift replan path (Phase 4)."""

from __future__ import annotations

from datetime import UTC, datetime

from agentic_calendar.common.clock import FrozenClock
from agentic_calendar.common.ids import DeterministicIdGenerator
from agentic_calendar.contracts.common_types import FocusLevel, TaskCategory
from agentic_calendar.contracts.reason_codes import ReasonCode
from agentic_calendar.contracts.task_plan import Task, TaskPlan
from agentic_calendar.contracts.user_duration_multipliers import (
    CategoryMultiplier,
    UserDurationMultipliers,
)
from agentic_calendar.planning import (
    LifecycleState,
    PlanVersion,
    propose_recalibrated_plan,
)

TS = datetime(2026, 5, 12, tzinfo=UTC)


def _task(tid: str, cat: TaskCategory, dur: int) -> Task:
    return Task(
        task_id=tid,
        module_id=f"m_{tid}",
        title=tid,
        estimated_duration_min=dur,
        cognitive_load=3,
        category=cat,
        required_focus_level=FocusLevel.MEDIUM,
    )


def _active_plan() -> PlanVersion:
    plan = TaskPlan(
        plan_version="plan_v1",
        tasks=[
            _task("t1", TaskCategory.PRACTICE, 90),
            _task("t2", TaskCategory.CONCEPT_REVIEW, 60),
        ],
    )
    return PlanVersion(
        plan_version="plan_v1",
        user_id="u1",
        state=LifecycleState.ACTIVE,
        plan=plan,
        created_at=TS,
        updated_at=TS,
    )


def _multipliers(factor: float) -> UserDurationMultipliers:
    return UserDurationMultipliers(
        user_id="u1",
        computed_at=TS,
        multipliers=[
            CategoryMultiplier(
                category=TaskCategory.PRACTICE,
                multiplier=factor,
                sample_size=6,
                observed_ratio=factor,
            )
        ],
    )


def _propose(active: PlanVersion, mult: UserDurationMultipliers):
    return propose_recalibrated_plan(
        active,
        mult,
        id_generator=DeterministicIdGenerator(),
        clock=FrozenClock(TS),
    )


def test_recalibration_produces_draft_with_scaled_durations() -> None:
    prop = _propose(_active_plan(), _multipliers(1.5))
    assert prop is not None
    durations = {t.task_id: t.estimated_duration_min for t in prop.draft.plan.tasks}
    assert durations == {"t1": 135, "t2": 60}  # only PRACTICE scaled


def test_draft_is_not_active_and_links_to_parent() -> None:
    """The replan is a draft; it must pass the approval gate before any write."""
    prop = _propose(_active_plan(), _multipliers(1.5))
    assert prop is not None
    assert prop.draft.state is LifecycleState.DRAFT
    assert prop.draft.parent_plan_version == "plan_v1"
    assert prop.draft.plan_version != "plan_v1"


def test_diff_carries_calibration_reason_code() -> None:
    prop = _propose(_active_plan(), _multipliers(1.5))
    assert prop is not None
    assert prop.diff.from_plan_version == "plan_v1"
    assert prop.diff.summary.tasks_with_duration_changes == 1
    assert prop.diff.summary.net_weekly_load_change_min == 45
    assert prop.diff.summary.modules_affected == ("m_t1",)
    assert all(
        fc.reason_code is ReasonCode.USER_DURATION_CALIBRATION
        for fc in prop.diff.field_changes
    )


def test_no_duration_change_returns_none() -> None:
    # A 1.0 multiplier moves nothing → no replan proposal.
    assert _propose(_active_plan(), _multipliers(1.0)) is None
    # An empty multiplier set likewise.
    empty = UserDurationMultipliers(user_id="u1", computed_at=TS)
    assert _propose(_active_plan(), empty) is None
