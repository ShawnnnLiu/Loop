"""Deterministic drop: remove tasks from the active plan, keep survivors in place.

A drop is a deterministic plan-version edit (NOT an LLM re-plan). It removes the
dropped tasks, prunes the dropped ids from every survivor's ``dependencies`` (so
no surviving task points at a vanished prerequisite — which would be an
``ORPHAN_DEPENDENCY`` at ``validation/graph.py``), and keeps every surviving
``task_id`` STABLE so the calendar mappings / diffs / drift that key on
``task_id`` keep working. Survivors keep their EXISTING placements (Open decision
#1): the new draft is the current draft with the dropped entries filtered out,
never a re-run of the scheduler.

Like ``recovery.py`` / ``replan.py`` this is pure: ``active`` / ``current_draft``
are never mutated, and the active :class:`PlanVersion` is never touched (a new
``DRAFT`` version is minted). The drop still flows through approval + a
delete-only calendar write before anything leaves the calendar.
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass
from datetime import datetime

from agentic_calendar.common.clock import Clock
from agentic_calendar.common.ids import IdGenerator
from agentic_calendar.contracts.draft_schedule import DraftSchedule
from agentic_calendar.contracts.plan_diff import (
    DiffChangeType,
    FieldChange,
    PlanDiff,
    PlanDiffSummary,
    TaskChange,
)
from agentic_calendar.contracts.reason_codes import ReasonCode
from agentic_calendar.contracts.task_plan import Task, TaskPlan

from .plan_version import (
    GenerationStep,
    GenerationStepRecord,
    LifecycleState,
    PlanVersion,
)


class DropError(ValueError):
    """A drop request that cannot be honored deterministically."""


@dataclass(frozen=True)
class DropProposal:
    """The deterministic outcome of one drop request.

    ``plan_version`` is the new ``DRAFT`` version (survivors only, edges pruned);
    ``draft_schedule`` carries the survivors at their EXISTING times; ``diff`` is
    the removal + edge-prune diff; ``dropped_ids`` and ``pruned_edges``
    (``(survivor, dropped_dependency)`` pairs) are the audit metadata.
    """

    plan_version: PlanVersion
    draft_schedule: DraftSchedule
    diff: PlanDiff
    dropped_ids: tuple[str, ...]
    pruned_edges: tuple[tuple[str, str], ...]


def propose_dropped_plan(
    active: PlanVersion,
    current_draft: DraftSchedule,
    dropped_ids: Collection[str],
    *,
    id_generator: IdGenerator,
    clock: Clock,
) -> DropProposal:
    """Build the drop proposal: remove ``dropped_ids`` from ``active``.

    Pure: ``active`` / ``current_draft`` are not mutated; replaying the same
    inputs (with the same injected clock + id generator) yields the same
    proposal. Rejects an unknown id or a request that would drop every task
    (:class:`DropError`).
    """
    plan_task_ids = {t.task_id for t in active.plan.tasks}
    drop_set = set(dropped_ids)
    if not drop_set:
        raise DropError("no tasks to drop")
    unknown = drop_set - plan_task_ids
    if unknown:
        raise DropError(f"unknown task_id(s): {sorted(unknown)}")
    if drop_set >= plan_task_ids:
        raise DropError("cannot drop every task in the plan")

    now = clock.now()
    to_version = id_generator.new_id("plan")

    survivors: list[Task] = []
    pruned_edges: list[tuple[str, str]] = []
    for task in active.plan.tasks:
        if task.task_id in drop_set:
            continue
        pruned = [dep for dep in task.dependencies if dep in drop_set]
        if pruned:
            pruned_edges.extend((task.task_id, dep) for dep in pruned)
            new_deps = [dep for dep in task.dependencies if dep not in drop_set]
            # Rebuild through validators (house rule: never model_copy past them).
            survivors.append(
                Task.model_validate({**task.model_dump(), "dependencies": new_deps})
            )
        else:
            survivors.append(task)

    new_plan = TaskPlan.model_validate(
        {"plan_version": to_version, "tasks": [t.model_dump() for t in survivors]}
    )
    plan_version = PlanVersion(
        plan_version=to_version,
        user_id=active.user_id,
        parent_plan_version=active.plan_version,
        state=LifecycleState.DRAFT,
        plan=new_plan,
        generation_history=[
            GenerationStepRecord(
                step=GenerationStep.NOTE,
                occurred_at=now,
                detail=(
                    f"drop from {active.plan_version}: removed {sorted(drop_set)}; "
                    f"pruned {len(pruned_edges)} dependency edge(s)"
                ),
            )
        ],
        created_at=now,
        updated_at=now,
    )

    # Survivors keep their EXISTING placements: filter the current draft's entries
    # to survivors, re-stamped under a fresh draft id + the new plan version.
    survivor_ids = {t.task_id for t in survivors}
    survivor_entries = tuple(
        e for e in current_draft.entries if e.task_id in survivor_ids
    )
    draft_schedule = DraftSchedule(
        draft_schedule_id=id_generator.new_id("draft"),
        plan_version=to_version,
        entries=survivor_entries,
        created_at=now,
    )

    diff = _build_diff(
        active=active,
        to_version=to_version,
        drop_set=drop_set,
        pruned_edges=pruned_edges,
        diff_id=id_generator.new_id("diff"),
        now=now,
    )
    return DropProposal(
        plan_version=plan_version,
        draft_schedule=draft_schedule,
        diff=diff,
        dropped_ids=tuple(sorted(drop_set)),
        pruned_edges=tuple(pruned_edges),
    )


def _build_diff(
    *,
    active: PlanVersion,
    to_version: str,
    drop_set: set[str],
    pruned_edges: list[tuple[str, str]],
    diff_id: str,
    now: datetime,
) -> PlanDiff:
    deps_by_task = {t.task_id: list(t.dependencies) for t in active.plan.tasks}
    dropped_duration = sum(
        t.estimated_duration_min for t in active.plan.tasks if t.task_id in drop_set
    )
    task_changes: list[TaskChange] = [
        TaskChange(
            task_id=tid,
            change_type=DiffChangeType.REMOVED,
            user_facing_summary=f"{tid} was dropped",
        )
        for tid in sorted(drop_set)
    ]
    pruned_survivors = sorted({survivor for survivor, _ in pruned_edges})
    field_changes: list[FieldChange] = []
    for survivor in pruned_survivors:
        dropped_deps = sorted(dep for s, dep in pruned_edges if s == survivor)
        task_changes.append(
            TaskChange(
                task_id=survivor,
                change_type=DiffChangeType.DEPENDENCY_CHANGED,
                user_facing_summary=(
                    f"{survivor} no longer depends on dropped {dropped_deps}"
                ),
            )
        )
        old_deps = deps_by_task[survivor]
        field_changes.append(
            FieldChange(
                task_id=survivor,
                field="dependencies",
                old_value=old_deps,
                new_value=[dep for dep in old_deps if dep not in drop_set],
                reason_code=ReasonCode.DEPENDENT_DROP_PRUNED,
            )
        )
    return PlanDiff(
        diff_id=diff_id,
        from_plan_version=active.plan_version,
        to_plan_version=to_version,
        computed_at=now,
        summary=PlanDiffSummary(
            tasks_added=0,
            tasks_removed=len(drop_set),
            tasks_rescheduled=0,
            tasks_with_duration_changes=0,
            modules_affected=(),
            net_weekly_load_change_min=-dropped_duration,
            timeline_change_days=0,
        ),
        task_changes=tuple(task_changes),
        field_changes=tuple(field_changes),
    )
