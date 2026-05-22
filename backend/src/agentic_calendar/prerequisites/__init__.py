"""Deterministic prerequisite logic (``docs/axioms/11-prerequisite-logic.md``).

``task_plan`` must not include ``prerequisites_met``; the runtime view here is
the single source of truth.
"""

from .compute import compute_runtime_view, eligible_task_ids
from .runtime_view import RuntimeTask, blocked_by, prerequisites_met

__all__ = [
    "RuntimeTask",
    "blocked_by",
    "compute_runtime_view",
    "eligible_task_ids",
    "prerequisites_met",
]
