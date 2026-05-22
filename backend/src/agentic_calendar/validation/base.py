"""Validation primitives shared by all five checkers.

Each checker is a pure function returning a list of ``Violation`` records.
None of them mutate their inputs (axiom 04). The orchestrator in
``__init__.py`` composes the five and produces a ``ValidationResult``.

Why functions and not classes: every checker is stateless. Functions keep the
public surface small and make ``mypy --strict`` straightforward.
"""

from __future__ import annotations

from typing import Any

from agentic_calendar.contracts.validation_result import Violation
from agentic_calendar.contracts.violation_types import ViolationType


def make_violation(
    type_: ViolationType,
    *,
    task_id: str | None = None,
    module_id: str | None = None,
    **details: Any,
) -> Violation:
    """Convenience constructor that drops ``None`` keys from ``details``."""
    cleaned = {k: v for k, v in details.items() if v is not None}
    return Violation(
        type=type_,
        task_id=task_id,
        module_id=module_id,
        details=cleaned,
    )
