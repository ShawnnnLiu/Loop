"""Deterministic recovery-plan draft path (Phase 7).

When the Accountability Policy Engine selects ``generate_recovery_plan_draft``
(``BEHIND_SCHEDULE_THRESHOLD_REACHED``, golden scenario 22), this builds the
recovery proposal. Like the duration-recalibration path (``replan.py``), it is
draft-only by construction: the active :class:`PlanVersion` is never touched,
and any draft still flows through validation, diff, and approval before a
calendar write.

Two routes, split by what the mode changes:

* ``reschedule`` — the **deterministic fast path**. Plan *content* is
  unchanged; only calendar placement will change, and placement is the
  Scheduler's job downstream. The draft is a new ``DRAFT`` plan version with
  identical tasks and an honest zero-change diff — claiming rescheduled tasks
  before the Scheduler runs would be fabricated data.
* ``scope_reduction`` / ``extend_timeline`` — these change plan content, and
  deterministic code must not invent content (LLMs propose, infrastructure
  disposes). The proposal routes to the LLM planner via the supervisor's
  ``REPLAN_REQUIRED → PLANNER_RUNNING`` edge, carrying the typed
  ``RECOVERY_PLAN_REQUIRED`` reason and the mode.

The composition root (operator CLI / future app layer) connects the policy
engine's decision to this function; ``accountability/`` itself never imports
``planning`` (leaf-region boundary).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from agentic_calendar.common.clock import Clock
from agentic_calendar.common.ids import IdGenerator
from agentic_calendar.contracts.checkin_event import RecoveryAction
from agentic_calendar.contracts.plan_diff import PlanDiff, PlanDiffSummary
from agentic_calendar.contracts.reason_codes import ReasonCode
from agentic_calendar.contracts.task_plan import TaskPlan

from .plan_version import (
    GenerationStep,
    GenerationStepRecord,
    LifecycleState,
    PlanVersion,
)


class RecoveryRoute(StrEnum):
    """How a recovery mode is fulfilled."""

    DETERMINISTIC_DRAFT = "deterministic_draft"
    PLANNER_REQUIRED = "planner_required"


@dataclass(frozen=True)
class RecoveryProposal:
    """The typed outcome of one recovery request.

    ``draft``/``diff`` are present exactly when ``route`` is
    ``DETERMINISTIC_DRAFT``; a ``PLANNER_REQUIRED`` proposal carries only the
    mode and reason for the supervisor to act on.
    """

    route: RecoveryRoute
    mode: RecoveryAction
    reason_code: ReasonCode
    draft: PlanVersion | None
    diff: PlanDiff | None


def propose_recovery_plan(
    active: PlanVersion,
    mode: RecoveryAction,
    *,
    id_generator: IdGenerator,
    clock: Clock,
) -> RecoveryProposal:
    """Build the recovery proposal for ``active`` under ``mode``.

    Pure: ``active`` is never mutated; replaying the same inputs (with the
    same injected clock and id generator) yields the same proposal.
    """
    if mode is not RecoveryAction.RESCHEDULE:
        return RecoveryProposal(
            route=RecoveryRoute.PLANNER_REQUIRED,
            mode=mode,
            reason_code=ReasonCode.RECOVERY_PLAN_REQUIRED,
            draft=None,
            diff=None,
        )

    now = clock.now()
    to_version = id_generator.new_id("plan")
    # Full re-validation on the version bump (house rule: never model_copy a
    # contract past its validators).
    new_plan = TaskPlan.model_validate({**active.plan.model_dump(), "plan_version": to_version})
    draft = PlanVersion(
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
                    f"recovery (reschedule) from {active.plan_version}: "
                    "content unchanged; scheduler re-places tasks"
                ),
            )
        ],
        created_at=now,
        updated_at=now,
    )
    diff = PlanDiff(
        diff_id=id_generator.new_id("diff"),
        from_plan_version=active.plan_version,
        to_plan_version=to_version,
        computed_at=now,
        summary=PlanDiffSummary(
            tasks_added=0,
            tasks_removed=0,
            tasks_rescheduled=0,
            tasks_with_duration_changes=0,
            modules_affected=(),
            net_weekly_load_change_min=0,
            timeline_change_days=0,
        ),
        task_changes=(),
        field_changes=(),
    )
    return RecoveryProposal(
        route=RecoveryRoute.DETERMINISTIC_DRAFT,
        mode=mode,
        reason_code=ReasonCode.RECOVERY_PLAN_REQUIRED,
        draft=draft,
        diff=diff,
    )
