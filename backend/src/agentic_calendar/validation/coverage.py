"""Syllabus coverage checks (axiom 04).

* every high-priority module has at least one task;
* every task references a valid ``module_id``;
* low-priority modules do not consume disproportionate time.

Tolerance for "disproportionate" is a heuristic prior; the threshold lives
here so it can be tuned without rewriting the orchestrator.
"""

from __future__ import annotations

from collections import defaultdict

from agentic_calendar.contracts.common_types import Priority
from agentic_calendar.contracts.syllabus_units import SyllabusUnits
from agentic_calendar.contracts.task_plan import TaskPlan
from agentic_calendar.contracts.validation_result import Violation
from agentic_calendar.contracts.violation_types import ViolationType

from .base import make_violation

LOW_PRIORITY_OVERWEIGHT_RATIO = 0.5
"""Heuristic prior: low-priority modules may not exceed 50% of total tasks' time."""


def check_coverage(plan: TaskPlan, syllabus: SyllabusUnits) -> list[Violation]:
    """Return coverage violations against the supplied syllabus."""
    violations: list[Violation] = []
    module_ids = {m.module_id for m in syllabus.modules}

    minutes_by_module: dict[str, int] = defaultdict(int)
    tasks_by_module: dict[str, int] = defaultdict(int)
    for t in plan.tasks:
        minutes_by_module[t.module_id] += t.estimated_duration_min
        tasks_by_module[t.module_id] += 1
        if t.module_id not in module_ids:
            violations.append(
                make_violation(
                    ViolationType.MISSING_MODULE_ID,
                    task_id=t.task_id,
                    module_id=t.module_id,
                )
            )

    for m in syllabus.modules:
        if m.priority is Priority.HIGH and tasks_by_module.get(m.module_id, 0) == 0:
            violations.append(
                make_violation(
                    ViolationType.MODULE_COVERAGE_MISSING,
                    module_id=m.module_id,
                    priority=m.priority.value,
                )
            )

    total_minutes = sum(minutes_by_module.values())
    if total_minutes > 0:
        for m in syllabus.modules:
            if m.priority is not Priority.LOW:
                continue
            module_minutes = minutes_by_module.get(m.module_id, 0)
            ratio = module_minutes / total_minutes
            if ratio > LOW_PRIORITY_OVERWEIGHT_RATIO:
                violations.append(
                    make_violation(
                        ViolationType.LOW_PRIORITY_MODULE_OVERWEIGHTED,
                        module_id=m.module_id,
                        module_minutes=module_minutes,
                        total_minutes=total_minutes,
                        ratio=round(ratio, 3),
                        max_ratio=LOW_PRIORITY_OVERWEIGHT_RATIO,
                    )
                )

    return violations
