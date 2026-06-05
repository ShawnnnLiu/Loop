"""Deterministic duration-calibration transform (Phase 4).

``apply_duration_calibration`` scales each task's ``estimated_duration_min`` by
the user's learned multiplier for that :class:`TaskCategory`, producing a new
:class:`TaskPlan` (a new version — the active plan is never mutated in place,
axiom 15) plus the plan-diff building blocks that record each change with the
``USER_DURATION_CALIBRATION`` reason code.

Determinism guarantees:

* A category with no learned multiplier (or a 1.0 multiplier) is a no-op.
* Rounding is round-half-up to a whole minute, floored at 1 (``estimated_duration_min``
  is ``gt=0``).
* Output ordering follows the input task order; same inputs ⇒ identical output.

The transform is pure: no clock, no id generation, no I/O. The caller
(``planning``) supplies the target ``plan_version`` (from its id generator) and
assembles the full :class:`~agentic_calendar.contracts.plan_diff.PlanDiff`
(which needs a clock + diff id) from the returned building blocks.
"""

from __future__ import annotations

from dataclasses import dataclass

from agentic_calendar.contracts.plan_diff import DiffChangeType, FieldChange, TaskChange
from agentic_calendar.contracts.reason_codes import ReasonCode
from agentic_calendar.contracts.task_plan import TaskPlan
from agentic_calendar.contracts.user_duration_multipliers import UserDurationMultipliers

_FIELD = "estimated_duration_min"


def _round_half_up(value: float) -> int:
    """Round to the nearest int, halves up. Deterministic for non-negative input."""
    return int(value + 0.5)


@dataclass(frozen=True)
class CalibrationResult:
    """Output of :func:`apply_duration_calibration`.

    ``plan`` always carries the requested ``to_plan_version``. When
    :attr:`changed` is ``False`` the tasks are identical to the input (only the
    version string differs) and the caller should typically skip persisting a
    new version.
    """

    plan: TaskPlan
    field_changes: tuple[FieldChange, ...]
    task_changes: tuple[TaskChange, ...]

    @property
    def changed(self) -> bool:
        return bool(self.field_changes)

    @property
    def changed_task_ids(self) -> tuple[str, ...]:
        return tuple(fc.task_id for fc in self.field_changes)


def apply_duration_calibration(
    plan: TaskPlan,
    multipliers: UserDurationMultipliers,
    *,
    to_plan_version: str,
) -> CalibrationResult:
    """Return a calibrated copy of ``plan`` at version ``to_plan_version``.

    Each task whose category has a learned multiplier != 1.0 (and whose rounded
    duration actually moves) is scaled; everything else is carried through
    unchanged.
    """
    factors = multipliers.as_map()

    new_tasks = []
    field_changes: list[FieldChange] = []
    task_changes: list[TaskChange] = []

    for task in plan.tasks:
        factor = factors.get(task.category)
        if factor is None or factor == 1.0:
            new_tasks.append(task)
            continue

        old = task.estimated_duration_min
        new = max(1, _round_half_up(old * factor))
        if new == old:
            new_tasks.append(task)
            continue

        # model_copy skips validators (Pydantic v2); `new` is always >= 1 from
        # the max() guard above, so Task's estimated_duration_min gt=0 holds.
        new_tasks.append(task.model_copy(update={_FIELD: new}))
        field_changes.append(
            FieldChange(
                task_id=task.task_id,
                field=_FIELD,
                old_value=old,
                new_value=new,
                delta_minutes=new - old,
                reason_code=ReasonCode.USER_DURATION_CALIBRATION,
            )
        )
        task_changes.append(
            TaskChange(
                task_id=task.task_id,
                change_type=DiffChangeType.DURATION_CHANGED,
                user_facing_summary=(
                    f"Estimated time updated from {old} to {new} min "
                    "based on your recent pace."
                ),
            )
        )

    new_plan = TaskPlan(plan_version=to_plan_version, tasks=new_tasks)
    return CalibrationResult(
        plan=new_plan,
        field_changes=tuple(field_changes),
        task_changes=tuple(task_changes),
    )
