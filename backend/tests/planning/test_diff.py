"""Tests for the deterministic plan-content diff (``planning/diff.py``, D4).

The diff is the review/approval surface's source of truth for "N changed,
M preserved" — these tests pin the id partitions (full-content equality),
the contract pieces (task/field changes, summary counts), the change-line
wording scaffolding, and the honesty edges (title-only rewording is CHANGED,
never preserved, even though the contract vocabulary cannot type it).
"""

from __future__ import annotations

from datetime import UTC, datetime

from agentic_calendar.contracts.common_types import FocusLevel, TaskCategory
from agentic_calendar.contracts.plan_diff import DiffChangeType
from agentic_calendar.contracts.reason_codes import ReasonCode
from agentic_calendar.contracts.task_plan import Task, TaskPlan
from agentic_calendar.planning.diff import as_plan_diff, diff_plan_content

_NOW = datetime(2026, 7, 5, 12, 0, tzinfo=UTC)


def _task(
    task_id: str,
    *,
    module_id: str = "m1",
    title: str | None = None,
    deps: list[str] | None = None,
    duration: int = 60,
) -> Task:
    return Task(
        task_id=task_id,
        module_id=module_id,
        title=title if title is not None else f"Task {task_id}",
        dependencies=deps or [],
        estimated_duration_min=duration,
        cognitive_load=3,
        category=TaskCategory.PRACTICE,
        required_focus_level=FocusLevel.DEEP,
    )


def _plan(version: str, tasks: list[Task]) -> TaskPlan:
    return TaskPlan(plan_version=version, tasks=tasks)


def test_identical_content_is_fully_preserved() -> None:
    tasks = [_task("a"), _task("b", deps=["a"])]
    diff = diff_plan_content(_plan("plan_old", tasks), _plan("plan_new", tasks))
    assert diff.preserved_ids == ("a", "b")
    assert diff.added_ids == diff.removed_ids == diff.changed_ids == ()
    assert diff.change_lines == ()
    assert diff.task_changes == ()
    assert diff.summary.net_weekly_load_change_min == 0
    assert diff.summary.modules_affected == ()


def test_added_removed_and_duration_change_partition_and_count() -> None:
    old = _plan("plan_old", [_task("a"), _task("b"), _task("c", duration=30)])
    new = _plan(
        "plan_new", [_task("a"), _task("c", duration=90), _task("d", duration=45)]
    )
    diff = diff_plan_content(old, new)

    assert diff.added_ids == ("d",)
    assert diff.removed_ids == ("b",)
    assert diff.changed_ids == ("c",)
    assert diff.preserved_ids == ("a",)
    # Removed → changed → added, deterministic order.
    assert diff.change_lines == (
        'Removed: "Task b"',
        '"Task c": 30 → 90 min',
        'Added: "Task d"',
    )
    assert diff.summary.tasks_added == 1
    assert diff.summary.tasks_removed == 1
    assert diff.summary.tasks_with_duration_changes == 1
    assert diff.summary.tasks_rescheduled == 0  # content diff: never fabricated
    # -60 (b removed) + 60 (c grew) + 45 (d added).
    assert diff.summary.net_weekly_load_change_min == 45
    assert diff.summary.modules_affected == ("m1",)

    kinds = {(tc.task_id, tc.change_type) for tc in diff.task_changes}
    assert kinds == {
        ("b", DiffChangeType.REMOVED),
        ("c", DiffChangeType.DURATION_CHANGED),
        ("d", DiffChangeType.ADDED),
    }
    (fc,) = diff.field_changes
    assert fc.task_id == "c"
    assert fc.field == "estimated_duration_min"
    assert (fc.old_value, fc.new_value, fc.delta_minutes) == (30, 90, 60)


def test_dependency_and_module_changes_are_typed_with_field_changes() -> None:
    old = _plan("plan_old", [_task("a"), _task("b", deps=["a"])])
    new = _plan(
        "plan_new", [_task("a", module_id="m2"), _task("b", deps=[])]
    )
    diff = diff_plan_content(old, new)

    assert diff.changed_ids == ("a", "b")
    kinds = {(tc.task_id, tc.change_type) for tc in diff.task_changes}
    assert kinds == {
        ("a", DiffChangeType.MODULE_REASSIGNED),
        ("b", DiffChangeType.DEPENDENCY_CHANGED),
    }
    fields = {(fc.task_id, fc.field) for fc in diff.field_changes}
    assert fields == {("a", "module_id"), ("b", "dependencies")}
    # Module reassignment touches both the old and new module.
    assert diff.summary.modules_affected == ("m1", "m2")
    assert '"Task a": module m1 → m2' in diff.change_lines
    assert '"Task b": prerequisites changed' in diff.change_lines


def test_dependency_order_alone_is_not_a_change() -> None:
    old = _plan("plan_old", [_task("a"), _task("b"), _task("c", deps=["a", "b"])])
    new = _plan("plan_new", [_task("a"), _task("b"), _task("c", deps=["b", "a"])])
    diff = diff_plan_content(old, new)
    # Full-content equality compares the list, so the reordered task is NOT
    # preserved — but the dependency SET is unchanged, so no
    # DEPENDENCY_CHANGED entry is fabricated either: it falls to the
    # unexpressible bucket ("details adjusted").
    assert diff.changed_ids == ("c",)
    assert diff.task_changes == ()
    assert '"Task c": details adjusted' in diff.change_lines


def test_title_only_rewording_is_changed_but_untyped() -> None:
    """A renamed task must never count as preserved (honesty), even though the
    plan-diff contract has no change type for it — it appears in the change
    lines and the changed partition, with no task_changes entry."""
    old = _plan("plan_old", [_task("a", title="Review DP states")])
    new = _plan("plan_new", [_task("a", title="Drill DP state design for Stripe")])
    diff = diff_plan_content(old, new)
    assert diff.changed_ids == ("a",)
    assert diff.preserved_ids == ()
    assert diff.task_changes == ()
    assert diff.change_lines == (
        '"Review DP states": now titled "Drill DP state design for Stripe"',
    )


def test_multiple_deltas_on_one_task_emit_multiple_typed_changes() -> None:
    old = _plan("plan_old", [_task("a", duration=60, deps=[])])
    new = _plan(
        "plan_new",
        [_task("a", duration=90, deps=["x"], module_id="m2", title="Renamed")],
    )
    # "x" is not defined in the new plan's tasks — TaskPlan doesn't enforce
    # graph closure (that's the validation layer), so the diff stays honest
    # about what the plans contain.
    diff = diff_plan_content(old, new)
    kinds = {tc.change_type for tc in diff.task_changes}
    assert kinds == {
        DiffChangeType.DURATION_CHANGED,
        DiffChangeType.DEPENDENCY_CHANGED,
        DiffChangeType.MODULE_REASSIGNED,
    }
    (line,) = diff.change_lines
    assert line.startswith('"Task a": ')
    assert "60 → 90 min" in line
    assert "prerequisites changed" in line
    assert "module m1 → m2" in line
    assert 'now titled "Renamed"' in line


def test_as_plan_diff_wraps_contract_with_uniform_reason() -> None:
    old = _plan("plan_old", [_task("a", duration=30), _task("b")])
    new = _plan("plan_new", [_task("a", duration=60), _task("b")])
    content = diff_plan_content(old, new)
    diff = as_plan_diff(
        content,
        diff_id="diff_001",
        now=_NOW,
        field_change_reason=ReasonCode.USER_DURATION_CALIBRATION,
    )
    assert diff.diff_id == "diff_001"
    assert diff.from_plan_version == "plan_old"
    assert diff.to_plan_version == "plan_new"
    assert diff.computed_at == _NOW
    assert diff.summary == content.summary
    assert diff.task_changes == content.task_changes
    assert [fc.reason_code for fc in diff.field_changes] == [
        ReasonCode.USER_DURATION_CALIBRATION
    ]
