"""Schema-shape checks for raw (pre-parsed) ``task_plan`` payloads.

Most schema checks are already enforced by the Pydantic contract in
``contracts.task_plan``. This module exists for two cases:

1. **Pre-parse validation**: the orchestrator sometimes receives raw dict
   data from an LLM node; this checker parses it via Pydantic and converts
   any ``ValidationError`` into structured ``Violation`` records.
2. **Forbidden-field surfacing**: if ``prerequisites_met`` slipped through,
   produce an explicit ``forbidden_field_present`` violation rather than
   relying on Pydantic's "extra fields not permitted" message.

When the input is already a parsed ``TaskPlan`` instance, this checker
returns no violations (Pydantic has already enforced the contract).
"""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from agentic_calendar.contracts.task_plan import TaskPlan
from agentic_calendar.contracts.validation_result import Violation
from agentic_calendar.contracts.violation_types import ViolationType

from .base import make_violation


def check_task_plan_shape(payload: TaskPlan | dict[str, Any]) -> list[Violation]:
    """Return shape-level violations for a candidate ``task_plan``.

    Accepts either a parsed ``TaskPlan`` (returns ``[]``) or a raw dict (which
    is parsed and any ``ValidationError`` is translated into structured
    violations).
    """
    if isinstance(payload, TaskPlan):
        return []
    try:
        TaskPlan.model_validate(payload)
    except ValidationError as exc:
        return _translate_pydantic_error(exc, payload)
    return []


def _translate_pydantic_error(
    exc: ValidationError, payload: dict[str, Any]
) -> list[Violation]:
    """Map Pydantic error entries to structured ``Violation`` records.

    Pydantic loses semantic detail in error messages, so we look at each
    ``loc`` tuple to pick the best ``ViolationType``. This mapping is
    intentionally small; specific cases are detected by the dedicated
    checkers (``graph``, ``coverage``, ``user_fit``).
    """
    violations: list[Violation] = []
    for err in exc.errors():
        loc = err["loc"]
        msg = err["msg"]
        task_id = _task_id_for_loc(loc, payload)

        # Forbidden field: axiom 11. The model-level validator raises with
        # the field name embedded in the message but with an empty loc, so we
        # also check for the field name in the surrounding payload.
        if "prerequisites_met" in msg or _payload_has_prerequisites_met(payload):
            offending_task_id = task_id or _first_task_with_prerequisites_met(payload)
            if offending_task_id is not None or "prerequisites_met" in msg:
                violations.append(
                    make_violation(
                        ViolationType.FORBIDDEN_FIELD_PRESENT,
                        task_id=offending_task_id,
                        field="prerequisites_met",
                        pydantic_message=msg,
                    )
                )
                continue

        # Unknown / extra field: extra="forbid" path.
        if err["type"] == "extra_forbidden":
            violations.append(
                make_violation(
                    ViolationType.FIELD_TYPE_INVALID,
                    task_id=task_id,
                    field=str(loc[-1]),
                    pydantic_message=msg,
                )
            )
            continue

        # Required-field missing.
        if err["type"] == "missing":
            violations.append(
                make_violation(
                    ViolationType.REQUIRED_FIELD_MISSING,
                    task_id=task_id,
                    field=".".join(str(p) for p in loc),
                    pydantic_message=msg,
                )
            )
            continue

        # Enum membership.
        if err["type"] in {"enum", "literal_error"}:
            violations.append(
                make_violation(
                    ViolationType.ENUM_VALUE_INVALID,
                    task_id=task_id,
                    field=".".join(str(p) for p in loc),
                    pydantic_message=msg,
                )
            )
            continue

        # Numeric range.
        if err["type"].startswith(("greater_than", "less_than", "int_")):
            violations.append(
                make_violation(
                    ViolationType.NUMERIC_OUT_OF_RANGE,
                    task_id=task_id,
                    field=".".join(str(p) for p in loc),
                    pydantic_message=msg,
                )
            )
            continue

        # Default fallback.
        violations.append(
            make_violation(
                ViolationType.FIELD_TYPE_INVALID,
                task_id=task_id,
                field=".".join(str(p) for p in loc),
                pydantic_message=msg,
            )
        )
    return violations


def _payload_has_prerequisites_met(payload: dict[str, Any]) -> bool:
    tasks = payload.get("tasks")
    if not isinstance(tasks, list):
        return False
    return any(
        isinstance(t, dict) and "prerequisites_met" in t for t in tasks
    )


def _first_task_with_prerequisites_met(payload: dict[str, Any]) -> str | None:
    tasks = payload.get("tasks")
    if not isinstance(tasks, list):
        return None
    for t in tasks:
        if isinstance(t, dict) and "prerequisites_met" in t:
            tid = t.get("task_id")
            if isinstance(tid, str):
                return tid
    return None


def _task_id_for_loc(loc: tuple[Any, ...], payload: dict[str, Any]) -> str | None:
    """Best-effort task_id lookup for a Pydantic error location.

    For ``loc=("tasks", 3, "estimated_duration_min")`` this returns
    ``payload["tasks"][3]["task_id"]`` if present.
    """
    if len(loc) >= 2 and loc[0] == "tasks" and isinstance(loc[1], int):
        tasks = payload.get("tasks")
        if isinstance(tasks, list) and 0 <= loc[1] < len(tasks):
            task = tasks[loc[1]]
            if isinstance(task, dict):
                tid = task.get("task_id")
                if isinstance(tid, str):
                    return tid
    return None
