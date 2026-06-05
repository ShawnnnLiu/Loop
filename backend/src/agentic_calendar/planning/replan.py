"""Deterministic duration-drift replan path (Phase 4).

When the drift classifier reports duration drift and calibration produces new
per-category multipliers, this builds the *draft* recalibrated plan version plus
the :class:`PlanDiff` that explains the change with the
``USER_DURATION_CALIBRATION`` reason code.

It is draft-only by construction: the new :class:`PlanVersion` is ``DRAFT``, so
it must still pass through the existing approval gate before any calendar write
(axiom: no calendar write without approval; "replanning recommendations do not
modify calendar events without approval"). This is the deterministic fast path
for duration drift; other drift types route through the LLM planner via the
supervisor's ``REPLAN_REQUIRED → PLANNER_RUNNING`` edge.

``planning`` may import the ``duration_estimation`` kernel (a shared leaf like
``prerequisites``); the kernel never imports back.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from agentic_calendar.common.clock import Clock
from agentic_calendar.common.ids import IdGenerator
from agentic_calendar.contracts.plan_diff import PlanDiff, PlanDiffSummary
from agentic_calendar.contracts.user_duration_multipliers import UserDurationMultipliers
from agentic_calendar.duration_estimation import (
    CalibrationResult,
    apply_duration_calibration,
)

from .plan_version import (
    GenerationStep,
    GenerationStepRecord,
    LifecycleState,
    PlanVersion,
)


@dataclass(frozen=True)
class RecalibrationProposal:
    """A draft recalibrated plan version and the diff that explains it."""

    draft: PlanVersion
    diff: PlanDiff
    calibration: CalibrationResult


def propose_recalibrated_plan(
    active: PlanVersion,
    multipliers: UserDurationMultipliers,
    *,
    id_generator: IdGenerator,
    clock: Clock,
) -> RecalibrationProposal | None:
    """Build a draft recalibrated plan version from ``active``.

    Returns ``None`` when calibration moves no task duration (nothing to
    recalibrate). The returned draft is in ``DRAFT`` state and is never written
    to a calendar without going through approval.
    """
    now = clock.now()
    to_version = id_generator.new_id("plan")
    result = apply_duration_calibration(
        active.plan, multipliers, to_plan_version=to_version
    )
    if not result.changed:
        return None

    draft = PlanVersion(
        plan_version=to_version,
        user_id=active.user_id,
        parent_plan_version=active.plan_version,
        state=LifecycleState.DRAFT,
        plan=result.plan,
        generation_history=[
            GenerationStepRecord(
                step=GenerationStep.NOTE,
                occurred_at=now,
                detail=(
                    "duration recalibration from "
                    f"{active.plan_version}: "
                    f"{len(result.field_changes)} task(s) adjusted"
                ),
            )
        ],
        created_at=now,
        updated_at=now,
    )

    diff = _build_diff(active, draft, result, now=now, id_generator=id_generator)
    return RecalibrationProposal(draft=draft, diff=diff, calibration=result)


def _build_diff(
    active: PlanVersion,
    draft: PlanVersion,
    result: CalibrationResult,
    *,
    now: datetime,
    id_generator: IdGenerator,
) -> PlanDiff:
    task_module = {t.task_id: t.module_id for t in active.plan.tasks}
    modules_affected = tuple(
        sorted({task_module[fc.task_id] for fc in result.field_changes})
    )
    # Plan-wide net minutes delta from recalibration. The contract field is
    # named for weekly load; the plan carries no week index here, so this is the
    # plan-wide net (per-week decomposition is a later refinement).
    net_change = sum(fc.delta_minutes or 0 for fc in result.field_changes)

    summary = PlanDiffSummary(
        tasks_added=0,
        tasks_removed=0,
        tasks_rescheduled=0,
        tasks_with_duration_changes=len(result.field_changes),
        modules_affected=modules_affected,
        net_weekly_load_change_min=net_change,
        timeline_change_days=0,
    )
    return PlanDiff(
        diff_id=id_generator.new_id("diff"),
        from_plan_version=active.plan_version,
        to_plan_version=draft.plan_version,
        computed_at=now,
        summary=summary,
        task_changes=result.task_changes,
        field_changes=result.field_changes,
    )
