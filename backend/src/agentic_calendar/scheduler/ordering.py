"""Pure deterministic task ordering for the greedy scheduler.

Order policy (per ``docs/axioms/05-scheduler-policy.md``):

1. Topological sort by dependency (parents first).
2. Higher-priority modules earlier (when priority is supplied).
3. Higher cognitive-load tasks earlier within each topological tier.
4. Stable on ``task_id`` so the order is reproducible.

We do not need a syllabus to schedule, so module priority is optional input.
When omitted, only topo + cognitive-load + task_id determine the order.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping

from agentic_calendar.contracts.common_types import Priority
from agentic_calendar.contracts.task_plan import Task, TaskPlan

PRIORITY_RANK: dict[Priority, int] = {
    Priority.HIGH: 0,
    Priority.MEDIUM: 1,
    Priority.LOW: 2,
}


def topological_order(
    plan: TaskPlan,
    *,
    module_priority: Mapping[str, Priority] | None = None,
) -> list[Task]:
    """Return the tasks in scheduler order.

    Uses Kahn's algorithm; within each "ready" tier we apply the priority and
    cognitive-load tiebreakers. Tasks with edges to non-existent IDs are
    treated as orphan-blocked here (the validator already rejected them, but
    this fallback keeps the function defensive).
    """
    by_id: dict[str, Task] = {t.task_id: t for t in plan.tasks}
    in_degree: dict[str, int] = {tid: 0 for tid in by_id}
    children: dict[str, list[str]] = defaultdict(list)

    for t in plan.tasks:
        for dep in t.dependencies:
            if dep in by_id:
                in_degree[t.task_id] += 1
                children[dep].append(t.task_id)

    ready: list[Task] = sorted(
        (t for t in plan.tasks if in_degree[t.task_id] == 0),
        key=lambda t: sort_key(t, module_priority),
    )
    out: list[Task] = []
    while ready:
        head = ready.pop(0)
        out.append(head)
        for child_id in children.get(head.task_id, []):
            in_degree[child_id] -= 1
            if in_degree[child_id] == 0:
                ready.append(by_id[child_id])
        ready.sort(key=lambda t: sort_key(t, module_priority))
    return out


def sort_key(
    task: Task, module_priority: Mapping[str, Priority] | None
) -> tuple[int, int, str]:
    """The deterministic ordering key (priority rank, cognitive load, task_id).

    Public because the greedy loop reuses it for insertion-order tie-breaks
    (axiom 05 "Insertion order") — one key definition, two consumers.
    """
    priority_rank = (
        PRIORITY_RANK.get(module_priority[task.module_id], len(PRIORITY_RANK))
        if module_priority is not None and task.module_id in module_priority
        else len(PRIORITY_RANK)
    )
    cognitive_rank = -task.cognitive_load
    return (priority_rank, cognitive_rank, task.task_id)
