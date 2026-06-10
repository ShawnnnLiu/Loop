"""Tests for ``planning.plan_version``."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from agentic_calendar.contracts.task_plan import TaskPlan
from agentic_calendar.planning.plan_version import (
    GenerationStep,
    GenerationStepRecord,
    LifecycleState,
    PlanVersion,
)
from tests._fixture_loader import iter_valid


def _now() -> datetime:
    return datetime(2026, 5, 4, 12, 0, 0, tzinfo=UTC)


def _plan() -> TaskPlan:
    return TaskPlan.model_validate(next(iter_valid("task_plan")).payload)


def _draft() -> PlanVersion:
    plan = _plan()
    return PlanVersion(
        plan_version=plan.plan_version,
        user_id="user_001",
        parent_plan_version=None,
        state=LifecycleState.DRAFT,
        plan=plan,
        generation_history=[],
        created_at=_now(),
        updated_at=_now(),
    )


def test_plan_version_must_match_inner_plan_version() -> None:
    plan = _plan()
    with pytest.raises(ValidationError):
        PlanVersion(
            plan_version="different",
            user_id="user_001",
            parent_plan_version=None,
            state=LifecycleState.DRAFT,
            plan=plan,
            generation_history=[],
            created_at=_now(),
            updated_at=_now(),
        )


def test_timestamps_must_be_aware() -> None:
    plan = _plan()
    with pytest.raises(ValidationError):
        PlanVersion(
            plan_version=plan.plan_version,
            user_id="user_001",
            parent_plan_version=None,
            state=LifecycleState.DRAFT,
            plan=plan,
            generation_history=[],
            created_at=datetime(2026, 5, 4, 12, 0, 0),
            updated_at=_now(),
        )


def test_append_history_returns_new_instance_with_record_appended() -> None:
    pv = _draft()
    record = GenerationStepRecord(
        step=GenerationStep.PLANNER, occurred_at=_now(), detail="initial"
    )
    new = pv.append_history(record, now=_now() + timedelta(seconds=10))
    assert new is not pv
    assert pv.generation_history == []
    assert new.generation_history == [record]
    assert new.updated_at == _now() + timedelta(seconds=10)


def test_append_history_rejects_now_before_created_at() -> None:
    # model_copy would let a stale clock violate updated_at >= created_at;
    # the evolution path must re-run validators (Pydantic v2 bypass guard).
    pv = _draft()
    record = GenerationStepRecord(
        step=GenerationStep.PLANNER, occurred_at=_now(), detail="initial"
    )
    with pytest.raises(ValidationError, match="must not precede created_at"):
        pv.append_history(record, now=_now() - timedelta(days=1))


def test_transition_to_rejects_now_before_created_at() -> None:
    pv = _draft()
    with pytest.raises(ValidationError, match="must not precede created_at"):
        pv.transition_to(LifecycleState.APPROVED, now=_now() - timedelta(days=1))


def test_transitions_draft_to_approved_to_active_to_discarded() -> None:
    pv = _draft()
    approved = pv.transition_to(LifecycleState.APPROVED, now=_now())
    assert approved.state is LifecycleState.APPROVED
    active = approved.transition_to(LifecycleState.ACTIVE, now=_now())
    assert active.state is LifecycleState.ACTIVE
    discarded = active.transition_to(LifecycleState.DISCARDED, now=_now())
    assert discarded.state is LifecycleState.DISCARDED


def test_forbidden_transition_raises() -> None:
    pv = _draft()
    with pytest.raises(ValueError, match="forbidden lifecycle"):
        pv.transition_to(LifecycleState.ACTIVE, now=_now())


def test_discarded_is_terminal() -> None:
    pv = _draft().transition_to(LifecycleState.DISCARDED, now=_now())
    for state in (
        LifecycleState.DRAFT,
        LifecycleState.APPROVED,
        LifecycleState.ACTIVE,
    ):
        with pytest.raises(ValueError):
            pv.transition_to(state, now=_now())


def test_generation_step_record_requires_aware_datetime() -> None:
    with pytest.raises(ValidationError):
        GenerationStepRecord(
            step=GenerationStep.PLANNER,
            occurred_at=datetime(2026, 5, 4, 12, 0, 0),
        )


def test_plan_version_is_frozen() -> None:
    pv = _draft()
    with pytest.raises(ValidationError):
        pv.state = LifecycleState.APPROVED  # type: ignore[misc]
