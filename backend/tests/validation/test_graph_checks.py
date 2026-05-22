"""Tests for ``validation.graph.check_task_graph``.

Covers axiom 04's graph-integrity contract: duplicates, orphans, cycles,
self-deps. Uses programmatic construction so we can build inputs the
contract would otherwise reject (the model rejects duplicates and self-deps
at parse time; we round-trip through the model so the test exercises the
checker, not the contract).
"""

from __future__ import annotations

import pytest

from agentic_calendar.contracts.violation_types import ViolationType
from agentic_calendar.validation.graph import check_task_graph
from tests.validation._helpers import make_plan, make_task


def test_clean_graph_has_no_violations() -> None:
    plan = make_plan(
        make_task(task_id="a"),
        make_task(task_id="b", dependencies=["a"]),
        make_task(task_id="c", dependencies=["b"]),
    )
    assert check_task_graph(plan) == []


def test_orphan_dependency_detected() -> None:
    plan = make_plan(
        make_task(task_id="a"),
        make_task(task_id="b", dependencies=["does_not_exist"]),
    )
    violations = check_task_graph(plan)
    assert len(violations) == 1
    v = violations[0]
    assert v.type is ViolationType.ORPHAN_DEPENDENCY
    assert v.task_id == "b"
    assert v.details["invalid_dependency"] == "does_not_exist"


def test_duplicate_task_id_rejected_by_model() -> None:
    """Contract-level rejection happens before this checker can fire.

    We document that here by asserting the model raises, ensuring the layered
    defense (contract first, checker second) is active.
    """
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        make_plan(
            make_task(task_id="a"),
            make_task(task_id="a", title="dup"),
        )


def test_self_dependency_rejected_by_model() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        make_plan(make_task(task_id="a", dependencies=["a"]))


def test_two_node_cycle_detected() -> None:
    """Build a 2-cycle by bypassing the contract via direct model construction.

    Contract: ``details["cycle_members"]`` is the unique cycle nodes, rotated
    to start at the lexicographically smallest member. A 2-cycle ``a <-> b``
    is reported as ``["a", "b"]`` (not ``["a", "b", "a"]``).
    """
    from agentic_calendar.contracts.common_types import FocusLevel, TaskCategory
    from agentic_calendar.contracts.task_plan import Task, TaskPlan

    a = Task.model_construct(
        task_id="a",
        module_id="dp",
        title="A",
        description="",
        dependencies=["b"],
        estimated_duration_min=60,
        cognitive_load=3,
        category=TaskCategory.PRACTICE,
        required_focus_level=FocusLevel.MEDIUM,
        splittable=False,
    )
    b = Task.model_construct(
        task_id="b",
        module_id="dp",
        title="B",
        description="",
        dependencies=["a"],
        estimated_duration_min=60,
        cognitive_load=3,
        category=TaskCategory.PRACTICE,
        required_focus_level=FocusLevel.MEDIUM,
        splittable=False,
    )
    plan = TaskPlan.model_construct(plan_version="p", tasks=[a, b])

    violations = check_task_graph(plan)
    cycle_violations = [
        v for v in violations if v.type is ViolationType.CYCLE_DETECTED
    ]
    assert len(cycle_violations) == 1
    assert cycle_violations[0].details["cycle_members"] == ["a", "b"]
    # The old "members" key must be gone — pin the contract.
    assert "members" not in cycle_violations[0].details


def test_three_node_cycle_detected() -> None:
    """A 3-cycle ``a -> b -> c -> a`` is reported as ``["a", "b", "c"]``."""
    from agentic_calendar.contracts.common_types import FocusLevel, TaskCategory
    from agentic_calendar.contracts.task_plan import Task, TaskPlan

    def t(task_id: str, deps: list[str]) -> Task:
        return Task.model_construct(
            task_id=task_id,
            module_id="dp",
            title=task_id,
            description="",
            dependencies=deps,
            estimated_duration_min=60,
            cognitive_load=3,
            category=TaskCategory.PRACTICE,
            required_focus_level=FocusLevel.MEDIUM,
            splittable=False,
        )

    plan = TaskPlan.model_construct(
        plan_version="p",
        tasks=[t("a", ["b"]), t("b", ["c"]), t("c", ["a"])],
    )
    violations = check_task_graph(plan)
    cycle_violations = [
        v for v in violations if v.type is ViolationType.CYCLE_DETECTED
    ]
    assert len(cycle_violations) == 1
    assert cycle_violations[0].details["cycle_members"] == ["a", "b", "c"]


def test_orphan_and_cycle_reported_independently() -> None:
    from agentic_calendar.contracts.common_types import FocusLevel, TaskCategory
    from agentic_calendar.contracts.task_plan import Task, TaskPlan

    def t(task_id: str, deps: list[str]) -> Task:
        return Task.model_construct(
            task_id=task_id,
            module_id="dp",
            title=task_id,
            description="",
            dependencies=deps,
            estimated_duration_min=60,
            cognitive_load=3,
            category=TaskCategory.PRACTICE,
            required_focus_level=FocusLevel.MEDIUM,
            splittable=False,
        )

    plan = TaskPlan.model_construct(
        plan_version="p",
        tasks=[t("a", ["b"]), t("b", ["a", "ghost"])],
    )
    violations = check_task_graph(plan)
    types = {v.type for v in violations}
    assert ViolationType.ORPHAN_DEPENDENCY in types
    assert ViolationType.CYCLE_DETECTED in types
