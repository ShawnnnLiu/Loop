"""Final pre-Scheduler gate.

Even after schema, graph, coverage, and user-fit pass, the Scheduler may
need a couple of structural assurances before it runs. This checker is the
last validator; if it returns an empty violation list, the Supervisor may
route to ``scheduler``.

Phase 1 checks:

* the plan must contain at least one task whose dependencies are satisfiable
  (i.e. at least one root task with no dependencies). Otherwise the
  Scheduler cannot place anything and would produce only
  ``DEPENDENCY_BLOCKED`` failures.
"""

from __future__ import annotations

from agentic_calendar.contracts.task_plan import TaskPlan
from agentic_calendar.contracts.validation_result import Violation
from agentic_calendar.contracts.violation_types import ViolationType

from .base import make_violation


def check_scheduling_preconditions(plan: TaskPlan) -> list[Violation]:
    """Return violations that would prevent the Scheduler from doing useful work."""
    if not plan.tasks:
        return []  # Empty-plans are a schema concern, not ours.
    has_root = any(not t.dependencies for t in plan.tasks)
    if has_root:
        return []
    return [
        make_violation(
            ViolationType.MISSING_MODULE_ID,
            details_summary="no_root_task",
            note=(
                "every task has at least one dependency; the scheduler would "
                "deadlock with DEPENDENCY_BLOCKED for every placement"
            ),
        )
    ]
