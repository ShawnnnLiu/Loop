"""Deterministic plan-content diff between two plan versions (UX pass D4).

The general old→new diff the replan flow surfaces at review/approval, so the
user evaluates the *delta* ("3 changed, 14 preserved") instead of re-reading a
wall of blocks. The diff is computed by code from the two persisted plans —
the LLM may summarize it, but never produces it (axiom 15; plan-diff spec).

Two layers:

* :func:`diff_plan_content` — the pure core. Partitions task ids into
  added / removed / changed / preserved by full content comparison, and builds
  the contract pieces (``TaskChange`` / ``FieldChange`` / ``PlanDiffSummary``)
  plus deterministic user-facing change lines. No ids, no clock — read
  projections may call it on every fetch.
* :func:`as_plan_diff` — wraps the core into the immutable
  :class:`~agentic_calendar.contracts.plan_diff.PlanDiff` contract (needs a
  ``diff_id`` and timestamp from the caller's injected generators).

Vocabulary note (honesty over completeness): the contract's change types
cover duration, dependency, and module changes plus added/removed. Content
changes outside that vocabulary — a reworded title or description, a
category / focus / load / splittable tweak — still count as "changed" in the
id partitions and change lines (a renamed task is NOT "preserved"), but they
appear in the contract's ``task_changes``/``field_changes`` only when the
task also has an expressible change. ``tasks_rescheduled`` stays 0 here:
this is a content diff, and placement is the Scheduler's output, not the
plan's — claiming rescheduled tasks from plan content would be fabricated
data (same stance as ``recovery.py``). The spec's ``plan_diff_log``
persistence is future work; every diff is recomputable from the two
persisted plan versions.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from agentic_calendar.contracts.plan_diff import (
    DiffChangeType,
    FieldChange,
    PlanDiff,
    PlanDiffSummary,
    TaskChange,
)
from agentic_calendar.contracts.reason_codes import ReasonCode
from agentic_calendar.contracts.task_plan import Task, TaskPlan


@dataclass(frozen=True)
class PlanContentDiff:
    """The pure content delta between two plans.

    ``changed_ids``/``preserved_ids`` partition the surviving tasks (present
    in both plans) by FULL content equality — a task is preserved only when
    every field matches. ``change_lines`` is one deterministic user-facing
    sentence per removed, changed, and added task (in that order; plan order
    within each group) — the compact list review surfaces render.
    """

    from_plan_version: str
    to_plan_version: str
    added_ids: tuple[str, ...]
    removed_ids: tuple[str, ...]
    changed_ids: tuple[str, ...]
    preserved_ids: tuple[str, ...]
    change_lines: tuple[str, ...]
    task_changes: tuple[TaskChange, ...]
    field_changes: tuple[FieldChange, ...]
    summary: PlanDiffSummary


def _changed_parts(old: Task, new: Task) -> list[str]:
    """Compact deterministic descriptions of every field-level difference."""
    parts: list[str] = []
    if old.estimated_duration_min != new.estimated_duration_min:
        parts.append(
            f"{old.estimated_duration_min} → {new.estimated_duration_min} min"
        )
    if sorted(old.dependencies) != sorted(new.dependencies):
        parts.append("prerequisites changed")
    if old.module_id != new.module_id:
        parts.append(f"module {old.module_id} → {new.module_id}")
    if old.title != new.title:
        parts.append(f'now titled "{new.title}"')
    if not parts:
        # Content differs only in fields with no compact rendering
        # (description, category, focus, load, splittable).
        parts.append("details adjusted")
    return parts


def diff_plan_content(old_plan: TaskPlan, new_plan: TaskPlan) -> PlanContentDiff:
    """Compute the deterministic content delta from ``old_plan`` to ``new_plan``.

    Pure: same plans in, same diff out; tasks are matched by ``task_id``.
    Field-level ``reason_code`` values are the caller's to choose via
    :func:`as_plan_diff` — this core records the structural facts only.
    """
    old_by_id = {t.task_id: t for t in old_plan.tasks}
    new_by_id = {t.task_id: t for t in new_plan.tasks}

    added = tuple(t.task_id for t in new_plan.tasks if t.task_id not in old_by_id)
    removed = tuple(t.task_id for t in old_plan.tasks if t.task_id not in new_by_id)
    changed = tuple(
        t.task_id
        for t in new_plan.tasks
        if t.task_id in old_by_id and old_by_id[t.task_id] != t
    )
    preserved = tuple(
        t.task_id
        for t in new_plan.tasks
        if t.task_id in old_by_id and old_by_id[t.task_id] == t
    )

    change_lines: list[str] = [
        f'Removed: "{old_by_id[tid].title}"' for tid in removed
    ]
    task_changes: list[TaskChange] = [
        TaskChange(
            task_id=tid,
            change_type=DiffChangeType.REMOVED,
            user_facing_summary=f'Removed: "{old_by_id[tid].title}"',
        )
        for tid in removed
    ]
    field_changes: list[FieldChange] = []
    modules_affected: set[str] = {old_by_id[tid].module_id for tid in removed}
    duration_change_count = 0

    for tid in changed:
        old, new = old_by_id[tid], new_by_id[tid]
        change_lines.append(f'"{old.title}": ' + ", ".join(_changed_parts(old, new)))
        if old.estimated_duration_min != new.estimated_duration_min:
            duration_change_count += 1
            task_changes.append(
                TaskChange(
                    task_id=tid,
                    change_type=DiffChangeType.DURATION_CHANGED,
                    user_facing_summary=(
                        f'"{old.title}": {old.estimated_duration_min} → '
                        f"{new.estimated_duration_min} minutes"
                    ),
                )
            )
            field_changes.append(
                FieldChange(
                    task_id=tid,
                    field="estimated_duration_min",
                    old_value=old.estimated_duration_min,
                    new_value=new.estimated_duration_min,
                    delta_minutes=(
                        new.estimated_duration_min - old.estimated_duration_min
                    ),
                    # Placeholder; as_plan_diff stamps the caller's reason.
                    reason_code=ReasonCode.DRIFT_REMEDIATION,
                )
            )
            modules_affected.update((old.module_id, new.module_id))
        if sorted(old.dependencies) != sorted(new.dependencies):
            task_changes.append(
                TaskChange(
                    task_id=tid,
                    change_type=DiffChangeType.DEPENDENCY_CHANGED,
                    user_facing_summary=f'"{old.title}": prerequisites changed',
                )
            )
            field_changes.append(
                FieldChange(
                    task_id=tid,
                    field="dependencies",
                    old_value=list(old.dependencies),
                    new_value=list(new.dependencies),
                    reason_code=ReasonCode.DRIFT_REMEDIATION,
                )
            )
            modules_affected.update((old.module_id, new.module_id))
        if old.module_id != new.module_id:
            task_changes.append(
                TaskChange(
                    task_id=tid,
                    change_type=DiffChangeType.MODULE_REASSIGNED,
                    user_facing_summary=(
                        f'"{old.title}": moved from module {old.module_id} '
                        f"to {new.module_id}"
                    ),
                )
            )
            field_changes.append(
                FieldChange(
                    task_id=tid,
                    field="module_id",
                    old_value=old.module_id,
                    new_value=new.module_id,
                    reason_code=ReasonCode.DRIFT_REMEDIATION,
                )
            )
            modules_affected.update((old.module_id, new.module_id))

    for tid in added:
        new = new_by_id[tid]
        change_lines.append(f'Added: "{new.title}"')
        task_changes.append(
            TaskChange(
                task_id=tid,
                change_type=DiffChangeType.ADDED,
                user_facing_summary=f'Added: "{new.title}"',
            )
        )
        modules_affected.add(new.module_id)

    # Plan-wide net minutes delta. The contract field is named for weekly
    # load; the plan carries no week index here, so this is the plan-wide
    # net (same reading as replan.py's calibration diff).
    net_change = sum(t.estimated_duration_min for t in new_plan.tasks) - sum(
        t.estimated_duration_min for t in old_plan.tasks
    )
    summary = PlanDiffSummary(
        tasks_added=len(added),
        tasks_removed=len(removed),
        tasks_rescheduled=0,
        tasks_with_duration_changes=duration_change_count,
        modules_affected=tuple(sorted(modules_affected)),
        net_weekly_load_change_min=net_change,
        timeline_change_days=0,
    )
    return PlanContentDiff(
        from_plan_version=old_plan.plan_version,
        to_plan_version=new_plan.plan_version,
        added_ids=added,
        removed_ids=removed,
        changed_ids=changed,
        preserved_ids=preserved,
        change_lines=tuple(change_lines),
        task_changes=tuple(task_changes),
        field_changes=tuple(field_changes),
        summary=summary,
    )


def as_plan_diff(
    content: PlanContentDiff,
    *,
    diff_id: str,
    now: datetime,
    field_change_reason: ReasonCode = ReasonCode.DRIFT_REMEDIATION,
) -> PlanDiff:
    """Wrap a content diff into the immutable ``PlanDiff`` contract.

    ``field_change_reason`` is the replan's typed driver, applied to every
    field change uniformly — deterministic code cannot attribute per-field
    causality inside a regenerated plan, so it must not pretend to. It must
    be one of the contract's allowed field-change reason codes.
    """
    field_changes = tuple(
        FieldChange.model_validate(
            {**fc.model_dump(), "reason_code": field_change_reason}
        )
        for fc in content.field_changes
    )
    return PlanDiff(
        diff_id=diff_id,
        from_plan_version=content.from_plan_version,
        to_plan_version=content.to_plan_version,
        computed_at=now,
        summary=content.summary,
        task_changes=content.task_changes,
        field_changes=field_changes,
    )
