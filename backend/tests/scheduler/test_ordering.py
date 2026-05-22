"""Tests for ``scheduler.ordering.topological_order``."""

from __future__ import annotations

from agentic_calendar.contracts.common_types import Priority
from agentic_calendar.scheduler.ordering import topological_order
from tests.scheduler._helpers import make_plan, make_task


def test_root_first_then_dependent() -> None:
    plan = make_plan(
        make_task(task_id="b", dependencies=["a"]),
        make_task(task_id="a"),
    )
    order = [t.task_id for t in topological_order(plan)]
    assert order == ["a", "b"]


def test_higher_cognitive_load_first_within_tier() -> None:
    plan = make_plan(
        make_task(task_id="lo", cognitive_load=1),
        make_task(task_id="hi", cognitive_load=5),
        make_task(task_id="md", cognitive_load=3),
    )
    order = [t.task_id for t in topological_order(plan)]
    assert order == ["hi", "md", "lo"]


def test_module_priority_breaks_ties() -> None:
    plan = make_plan(
        make_task(task_id="api1", module_id="api_design", cognitive_load=3),
        make_task(task_id="dp1", module_id="dp", cognitive_load=3),
    )
    priorities = {"dp": Priority.HIGH, "api_design": Priority.MEDIUM}
    order = [t.task_id for t in topological_order(plan, module_priority=priorities)]
    assert order == ["dp1", "api1"]


def test_stable_on_task_id_when_all_else_equal() -> None:
    plan = make_plan(
        make_task(task_id="b", cognitive_load=3),
        make_task(task_id="a", cognitive_load=3),
    )
    order = [t.task_id for t in topological_order(plan)]
    assert order == ["a", "b"]
