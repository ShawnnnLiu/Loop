"""Tests for the deterministic drop transform (``planning/drop.py``)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from agentic_calendar.common.clock import FrozenClock
from agentic_calendar.common.ids import DeterministicIdGenerator
from agentic_calendar.contracts.common_types import FocusLevel, TaskCategory
from agentic_calendar.contracts.draft_schedule import DraftSchedule, DraftScheduleEntry
from agentic_calendar.contracts.plan_diff import DiffChangeType
from agentic_calendar.contracts.reason_codes import ReasonCode
from agentic_calendar.contracts.task_plan import Task, TaskPlan
from agentic_calendar.planning.drop import DropError, propose_dropped_plan
from agentic_calendar.planning.plan_version import LifecycleState, PlanVersion

_NOW = datetime(2026, 5, 4, 12, 0, tzinfo=UTC)


def _task(task_id: str, deps: list[str]) -> Task:
    return Task(
        task_id=task_id,
        module_id="m1",
        title="t",
        dependencies=deps,
        estimated_duration_min=60,
        cognitive_load=3,
        category=TaskCategory.PRACTICE,
        required_focus_level=FocusLevel.DEEP,
    )


def _active() -> PlanVersion:
    plan = TaskPlan(
        plan_version="plan_seed",
        tasks=[
            _task("dp_001", []),
            _task("dp_002", ["dp_001"]),
            _task("dp_003", ["dp_001", "dp_002"]),
        ],
    )
    return PlanVersion(
        plan_version="plan_seed",
        user_id="user_1",
        parent_plan_version=None,
        state=LifecycleState.ACTIVE,
        plan=plan,
        generation_history=[],
        created_at=_NOW,
        updated_at=_NOW,
    )


def _draft() -> DraftSchedule:
    base = _NOW + timedelta(days=1)
    return DraftSchedule(
        draft_schedule_id="draft_001",
        plan_version="plan_seed",
        entries=(
            DraftScheduleEntry(
                task_id="dp_001", start=base, end=base + timedelta(minutes=60)
            ),
            DraftScheduleEntry(
                task_id="dp_002",
                start=base + timedelta(hours=2),
                end=base + timedelta(hours=3),
            ),
            DraftScheduleEntry(
                task_id="dp_003",
                start=base + timedelta(hours=4),
                end=base + timedelta(hours=5),
            ),
        ),
        created_at=_NOW,
    )


def _propose(dropped: set[str]) -> object:
    return propose_dropped_plan(
        _active(),
        _draft(),
        dropped,
        id_generator=DeterministicIdGenerator(),
        clock=FrozenClock(_NOW),
    )


def test_drop_removes_task_and_prunes_dependents() -> None:
    proposal = propose_dropped_plan(
        _active(),
        _draft(),
        {"dp_002"},
        id_generator=DeterministicIdGenerator(),
        clock=FrozenClock(_NOW),
    )
    survivors = {t.task_id: t for t in proposal.plan_version.plan.tasks}
    assert set(survivors) == {"dp_001", "dp_003"}
    assert survivors["dp_003"].dependencies == ["dp_001"]  # dp_002 pruned out
    assert survivors["dp_001"].dependencies == []
    assert proposal.dropped_ids == ("dp_002",)
    assert proposal.pruned_edges == (("dp_003", "dp_002"),)
    assert proposal.plan_version.state is LifecycleState.DRAFT
    assert proposal.plan_version.parent_plan_version == "plan_seed"


def test_drop_keeps_survivor_placements() -> None:
    proposal = propose_dropped_plan(
        _active(),
        _draft(),
        {"dp_002"},
        id_generator=DeterministicIdGenerator(),
        clock=FrozenClock(_NOW),
    )
    draft = proposal.draft_schedule
    assert [e.task_id for e in draft.entries] == ["dp_001", "dp_003"]
    original = {e.task_id: (e.start, e.end) for e in _draft().entries}
    for entry in draft.entries:
        assert (entry.start, entry.end) == original[entry.task_id]
    assert draft.plan_version == proposal.plan_version.plan_version


def test_drop_diff_records_removal_and_prune() -> None:
    proposal = propose_dropped_plan(
        _active(),
        _draft(),
        {"dp_002"},
        id_generator=DeterministicIdGenerator(),
        clock=FrozenClock(_NOW),
    )
    diff = proposal.diff
    assert diff.summary.tasks_removed == 1
    assert diff.summary.net_weekly_load_change_min == -60
    removed = {
        tc.task_id
        for tc in diff.task_changes
        if tc.change_type is DiffChangeType.REMOVED
    }
    assert removed == {"dp_002"}
    dep_changed = {
        tc.task_id
        for tc in diff.task_changes
        if tc.change_type is DiffChangeType.DEPENDENCY_CHANGED
    }
    assert dep_changed == {"dp_003"}
    fc = {f.task_id: f for f in diff.field_changes}
    assert fc["dp_003"].reason_code is ReasonCode.DEPENDENT_DROP_PRUNED
    assert fc["dp_003"].old_value == ["dp_001", "dp_002"]
    assert fc["dp_003"].new_value == ["dp_001"]


def test_drop_is_deterministic() -> None:
    assert _propose({"dp_002"}) == _propose({"dp_002"})


def test_drop_rejects_unknown_task() -> None:
    with pytest.raises(DropError, match="unknown task_id"):
        _propose({"ghost_999"})


def test_drop_rejects_dropping_all_tasks() -> None:
    with pytest.raises(DropError, match="every task"):
        _propose({"dp_001", "dp_002", "dp_003"})
