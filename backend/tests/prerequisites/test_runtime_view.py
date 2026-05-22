"""Tests for the prerequisite primitive functions and ``RuntimeTask``."""

from __future__ import annotations

from agentic_calendar.prerequisites.runtime_view import (
    RuntimeTask,
    blocked_by,
    prerequisites_met,
)


def test_no_dependencies_always_met() -> None:
    assert prerequisites_met([], []) is True
    assert prerequisites_met([], ["x"]) is True


def test_single_dependency_completed() -> None:
    assert prerequisites_met(["a"], ["a"]) is True


def test_single_dependency_not_completed() -> None:
    assert prerequisites_met(["a"], []) is False
    assert prerequisites_met(["a"], ["b"]) is False


def test_multiple_dependencies_partial() -> None:
    assert prerequisites_met(["a", "b"], ["a"]) is False
    assert prerequisites_met(["a", "b"], ["a", "b"]) is True
    assert prerequisites_met(["a", "b"], ["b", "a", "c"]) is True


def test_blocked_by_preserves_input_order() -> None:
    assert blocked_by(["c", "a", "b"], ["a"]) == ["c", "b"]


def test_blocked_by_empty_when_all_complete() -> None:
    assert blocked_by(["a", "b"], ["a", "b", "c"]) == []


def test_runtime_task_is_frozen() -> None:
    rt = RuntimeTask(
        task_id="t1",
        prerequisites_met=False,
        blocked_by=["t0"],
        eligible_for_scheduling=False,
    )
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        rt.prerequisites_met = True  # type: ignore[misc]
