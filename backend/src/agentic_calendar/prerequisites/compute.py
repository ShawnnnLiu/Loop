"""Compute the runtime view for an entire ``TaskPlan``.

This module turns a static ``TaskPlan`` plus a set of completed task IDs
into a list of ``RuntimeTask`` records. The Scheduler consumes this view to
decide which tasks are eligible for placement; it is the single place where
"is this task ready to run?" is answered.

We do not depend on ``contracts.task_plan.TaskPlan`` here for typing only —
the function takes the plan as input and returns runtime views, never
mutating the input. Validation runs upstream; this module assumes the input
plan is structurally valid.
"""

from __future__ import annotations

from collections.abc import Iterable

from agentic_calendar.contracts.task_plan import TaskPlan

from .runtime_view import RuntimeTask, blocked_by, prerequisites_met


def compute_runtime_view(
    plan: TaskPlan,
    *,
    completed_task_ids: Iterable[str] = (),
) -> list[RuntimeTask]:
    """Project a ``TaskPlan`` to ``RuntimeTask`` records.

    The result preserves the input task order. ``eligible_for_scheduling``
    is currently identical to ``prerequisites_met`` (see axiom 11; future
    phases may add additional gates such as schedule windows).
    """
    completed = set(completed_task_ids)
    runtime: list[RuntimeTask] = []
    for task in plan.tasks:
        met = prerequisites_met(task.dependencies, completed)
        runtime.append(
            RuntimeTask(
                task_id=task.task_id,
                prerequisites_met=met,
                blocked_by=blocked_by(task.dependencies, completed),
                eligible_for_scheduling=met,
            )
        )
    return runtime


def eligible_task_ids(
    plan: TaskPlan,
    *,
    completed_task_ids: Iterable[str] = (),
) -> list[str]:
    """Convenience wrapper: return only the task IDs the Scheduler may place."""
    return [
        rt.task_id
        for rt in compute_runtime_view(plan, completed_task_ids=completed_task_ids)
        if rt.eligible_for_scheduling
    ]
