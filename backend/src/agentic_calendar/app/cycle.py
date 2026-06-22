"""The deterministic operator cycle: onboard → propose → approve → write → ingest.

Every method drives the supervisor's ``route()`` table edge by edge and
persists a :class:`~agentic_calendar.app.state.RunRecord` after each
transition, so a later CLI invocation (or a crash) resumes from explicit,
typed control-plane state. LLM nodes are invoked only where the state machine
says an LLM node runs; their output passes boundary validation before any
deterministic consumer touches it, and their failures surface as typed
``reason_code`` values via ``ERROR_REQUIRES_USER`` — never as routing input.

This module also closes the deferred Phase 7 item: the
``REPLAN_REQUIRED → (REPLAN_STARTED) → PLANNER_RUNNING`` recovery route is
wired here. ``ingest`` classifies drift and accountability deterministically
and may park a run in ``REPLAN_REQUIRED``; ``propose`` then continues it —
through ``planning.recovery`` / ``planning.replan`` for deterministic drafts,
or back through the Planner node when recovery needs new plan content
(deterministic code must not invent content).

Bounded loops (axiom 04/05): at most ``MAX_REPAIR_ATTEMPTS_LLM`` (2) repair
re-prompts per artifact and at most :data:`MAX_SCHEDULER_PLANNER_ITERATIONS`
(2) Scheduler→Planner iterations; exhaustion routes to
``ERROR_REQUIRES_USER`` with the typed reason preserved.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from agentic_calendar.accountability.checkin import CheckinStatus, evaluate_checkin
from agentic_calendar.accountability.contract import derive_accountability_contract
from agentic_calendar.accountability.policy_engine import (
    AccountabilityOutcome,
    evaluate_accountability,
)
from agentic_calendar.accountability.projection import ProjectionInput
from agentic_calendar.accountability.recommitment import request_recommitment
from agentic_calendar.calendar_writer.manager import WriteStatus
from agentic_calendar.common.errors import AgenticCalendarError
from agentic_calendar.contracts.accountability_intervention import (
    AccountabilityAction,
    InterventionDecision,
)
from agentic_calendar.contracts.accountability_state import AccountabilityState
from agentic_calendar.contracts.approval_event import (
    ApprovalActionType,
    ApprovalEvent,
    HashAlgorithm,
)
from agentic_calendar.contracts.checkin_event import RecoveryAction
from agentic_calendar.contracts.data_access_audit import (
    DataAccessor,
    DataAccessPurpose,
)
from agentic_calendar.contracts.draft_schedule import DraftSchedule
from agentic_calendar.contracts.drift_event import DriftEvent, RecommendedPolicyAction
from agentic_calendar.contracts.hashing import canonical_payload_hash
from agentic_calendar.contracts.motivation_profile import RecoveryPreference
from agentic_calendar.contracts.reason_codes import ReasonCode
from agentic_calendar.contracts.scheduler_output import SchedulerOutput, ScheduleStatus
from agentic_calendar.contracts.syllabus_units import SyllabusUnits
from agentic_calendar.contracts.task_plan import TaskPlan
from agentic_calendar.contracts.telemetry import TelemetryEvent
from agentic_calendar.contracts.validation_result import (
    MAX_REPAIR_ATTEMPTS_LLM,
    NextAction,
    ValidationResult,
)
from agentic_calendar.drift.classifier import DriftInput
from agentic_calendar.duration_estimation.pooled import resolve_effective_multipliers
from agentic_calendar.llm_nodes.base import LLMNodeError
from agentic_calendar.llm_nodes.user_facing_explanation import UserExplanation
from agentic_calendar.planning.plan_version import (
    GenerationStep,
    GenerationStepRecord,
    LifecycleState,
    PlanVersion,
)
from agentic_calendar.planning.recovery import RecoveryRoute, propose_recovery_plan
from agentic_calendar.planning.replan import propose_recalibrated_plan
from agentic_calendar.scheduler import schedule
from agentic_calendar.scheduler.adjustment import DraftAdjustment, validate_placements
from agentic_calendar.scheduler.inputs import FreeBusyInterval, SchedulerInput
from agentic_calendar.scheduler.policy import policy_from_user_profile
from agentic_calendar.supervisor.routing import route
from agentic_calendar.supervisor.state import SupervisorSignal as Sig
from agentic_calendar.supervisor.state import SupervisorState as S
from agentic_calendar.telemetry.calibration import calibrate
from agentic_calendar.telemetry.metrics import completion_rate
from agentic_calendar.validation import validate_syllabus_units, validate_task_plan

from .environment import AppEnvironment
from .results import (
    AccountabilityResult,
    AdjustResult,
    AdjustViolation,
    ApproveResult,
    DraftView,
    IngestResult,
    MeResult,
    OnboardResult,
    ProposeResult,
    StatusResult,
    TelemetryItemOutcome,
    ThresholdFieldView,
    ThresholdSectionView,
    ThresholdsResult,
    TodayResult,
    TodayTask,
    WriteCycleResult,
)
from .state import OnboardingRecord, ReplanKind, RunRecord
from .tuning import TUNABLE_SECTIONS, scalar_fields

MAX_SCHEDULER_PLANNER_ITERATIONS = 2
"""Axiom 05 bound: at most two Scheduler→Planner iterations per run."""

DEFAULT_APPROVAL_TTL = timedelta(days=7)
"""Dogfood approvals must survive a human-paced approve→write gap, but still
expire: a week-old unexecuted approval requires an explicit re-approve."""

DEFAULT_TARGET_CALENDAR_ID = "agentic-calendar-dogfood"
"""Writes go to a dedicated secondary calendar only (axiom 06; Phase 9c)."""

HASH_CANONICALIZATION_VERSION = "v1"

#: Drift recommendation → deterministic recovery mode, for drift that fires
#: without an accountability recovery decision. ``None`` means the drift is
#: surfaced (reflection, status) but does not require a replan on its own —
#: content-shaping suggestions stay advisory until the user acts (replanning
#: is user-approved, never autonomous). Duration drift is handled separately
#: (recalibration path), so it maps to ``None`` here.
DRIFT_ACTION_TO_RECOVERY_MODE: Mapping[
    RecommendedPolicyAction, RecoveryAction | None
] = {
    RecommendedPolicyAction.REDUCE_WEEKLY_LOAD: RecoveryAction.SCOPE_REDUCTION,
    RecommendedPolicyAction.RESCHEDULE_AROUND_CONFLICT: RecoveryAction.RESCHEDULE,
    RecommendedPolicyAction.RESCHEDULE_PREREQUISITE_FIRST: RecoveryAction.RESCHEDULE,
    RecommendedPolicyAction.INCREASE_DURATION_ESTIMATES_FOR_CATEGORY: None,
    RecommendedPolicyAction.DECREASE_DURATION_ESTIMATES_FOR_CATEGORY: None,
    RecommendedPolicyAction.SPLIT_TOPIC_INTO_SMALLER_TASKS: None,
    RecommendedPolicyAction.ASK_USER_TO_ADJUST_GOAL: None,
    RecommendedPolicyAction.REVISE_ACCOUNTABILITY_CONTRACT: None,
    RecommendedPolicyAction.SWITCH_TO_PRIVATE_RECOVERY: None,
}


class CycleError(AgenticCalendarError):
    """An operator-command precondition failed (wrong state, missing record).

    Distinct from workflow failures: those land the run in
    ``ERROR_REQUIRES_USER`` with a typed ``reason_code``; this exception means
    the command itself was not applicable (e.g. ``approve`` before ``propose``).
    """


@dataclass(frozen=True, slots=True)
class _AccountabilityPass:
    """One accountability evaluation plus the audit ids of its side effects."""

    outcome: AccountabilityOutcome | None
    nudge_id: str | None
    recommitment_request_id: str | None


@dataclass(frozen=True, slots=True)
class AccountabilitySnapshot:
    """Read-only accountability projection for the dashboard.

    The pure result of one accountability pass — the weekly check-in status,
    the deterministic state, and the policy decision (with its full audit) —
    carrying none of the side effects ``_evaluate_accountability`` performs.
    """

    checkin_status: CheckinStatus
    state: AccountabilityState
    decision: InterventionDecision


@dataclass(frozen=True, slots=True)
class _ReplanDecision:
    """Deterministic replan verdict for one assessment."""

    kind: ReplanKind | None
    mode: RecoveryAction | None
    pending_user_choice: bool
    reason_code: ReasonCode | None

    @property
    def required(self) -> bool:
        return self.kind is not None


class CycleService:
    """Drives the full loop over one :class:`AppEnvironment`."""

    def __init__(self, env: AppEnvironment) -> None:
        self._env = env

    # ------------------------------------------------------------------ #
    # onboard
    # ------------------------------------------------------------------ #

    def onboard(self, payload: Mapping[str, Any]) -> OnboardResult:
        """Validate and persist the onboarding bundle.

        ``payload`` keys: ``user_profile`` (required), ``timezone`` (IANA,
        default UTC), ``motivation_profile`` (optional). Re-onboarding the
        same user replaces the bundle (profile edits are expected during
        dogfooding) but keeps the original ``created_at``.
        """
        env = self._env
        now = env.clock.now()
        profile = payload.get("user_profile")
        record = OnboardingRecord.model_validate(
            {
                "user_id": profile.get("user_id") if isinstance(profile, Mapping) else None,
                "user_profile": profile,
                "timezone": payload.get("timezone", "UTC"),
                "motivation_profile": payload.get("motivation_profile"),
                "created_at": now,
                "updated_at": now,
            }
        )
        prior = env.state.get_onboarding(record.user_id)
        if prior is not None:
            record = OnboardingRecord.model_validate(
                record.model_dump() | {"created_at": prior.created_at}
            )
        env.state.save_onboarding(record)
        return OnboardResult(
            user_id=record.user_id,
            created=prior is None,
            timezone=record.timezone,
            has_motivation_profile=record.motivation_profile is not None,
        )

    # ------------------------------------------------------------------ #
    # run-record helpers
    # ------------------------------------------------------------------ #

    def _save_run(self, record: RunRecord, **updates: Any) -> RunRecord:
        """Rebuild (house rule: through full validation) and persist."""
        updated = RunRecord.model_validate(
            record.model_dump() | updates | {"updated_at": self._env.clock.now()}
        )
        self._env.state.save_run(updated)
        return updated

    def _transition(self, record: RunRecord, signal: Sig, **updates: Any) -> RunRecord:
        """One supervisor edge: route, persist, return the new record."""
        next_state = route(record.state, signal)
        return self._save_run(record, state=next_state, **updates)

    def _require_onboarding(self, user_id: str) -> OnboardingRecord:
        record = self._env.state.get_onboarding(user_id)
        if record is None:
            raise CycleError(f"user {user_id!r} is not onboarded; run onboard first")
        return record

    def _require_run(self, user_id: str, run_id: str | None, *, expected: S) -> RunRecord:
        env = self._env
        run = (
            env.state.get_run(run_id)
            if run_id is not None
            else env.state.latest_run_for_user(user_id)
        )
        if run is None:
            raise CycleError(f"no run found for user {user_id!r}")
        if run.user_id != user_id:
            raise CycleError(f"run {run.run_id!r} belongs to a different user")
        if run.state is not expected:
            raise CycleError(
                f"run {run.run_id!r} is in state {run.state.value!r}; "
                f"this command requires {expected.value!r}"
            )
        return run

    # ------------------------------------------------------------------ #
    # propose
    # ------------------------------------------------------------------ #

    def propose(
        self,
        user_id: str,
        *,
        free_busy: Sequence[Mapping[str, Any]] = (),
        horizon_days: int | None = None,
        recovery_mode: RecoveryAction | None = None,
    ) -> ProposeResult:
        """Produce a draft plan + draft schedule awaiting approval.

        Fresh cycle: INITIAL → Strategist → validation → Planner → validation
        → Scheduler → AWAITING_USER_APPROVAL. If the user's latest run is
        parked in ``REPLAN_REQUIRED`` (set by ``ingest``), this continues it
        instead: ``REPLAN_STARTED`` re-enters the planner stage through the
        recovery or recalibration path. ``recovery_mode`` supplies the user's
        choice when the motivation profile says ``ask_each_time``.

        ``horizon_days`` defaults to the profile's full timeline
        (``timeline_weeks * 7``): user-fit validation sizes the plan to
        ``weekly_hours * timeline_weeks``, so the Phase 1 scheduler — which
        places the WHOLE plan inside the horizon — must be given the whole
        timeline. A shorter explicit horizon makes a full-sized plan
        structurally unschedulable (capacity failures cascading into
        ``DEPENDENCY_BLOCKED`` for every dependent task).
        """
        onboarding = self._require_onboarding(user_id)
        if horizon_days is None:
            horizon_days = onboarding.user_profile.timeline_weeks * 7
        latest = self._env.state.latest_run_for_user(user_id)
        if latest is not None and latest.state is S.REPLAN_REQUIRED:
            return self._propose_replan(
                onboarding,
                latest,
                recovery_mode=recovery_mode,
                free_busy=free_busy,
                horizon_days=horizon_days,
            )
        return self._propose_fresh(
            onboarding, free_busy=free_busy, horizon_days=horizon_days
        )

    def _propose_fresh(
        self,
        onboarding: OnboardingRecord,
        *,
        free_busy: Sequence[Mapping[str, Any]],
        horizon_days: int,
    ) -> ProposeResult:
        env = self._env
        profile = onboarding.user_profile
        now = env.clock.now()
        run = RunRecord(
            run_id=env.id_generator.new_id("run"),
            user_id=onboarding.user_id,
            state=S.INITIAL,
            created_at=now,
            updated_at=now,
        )
        env.state.save_run(run)
        run = self._transition(run, Sig.USER_PROFILE_COLLECTED)

        claims = list(env.claim_store.all())
        registry = {c.claim_id: c for c in claims}

        syllabus: SyllabusUnits | None = None
        for attempt in range(MAX_REPAIR_ATTEMPTS_LLM + 1):
            try:
                candidate = env.nodes.strategist.run(
                    run_id=run.run_id, user_profile=profile, source_claims=claims
                )
            except LLMNodeError as exc:
                return self._propose_failure(self._llm_failure(run, exc))
            run = self._transition(run, Sig.STRATEGIST_OUTPUT_PRODUCED)
            result = validate_syllabus_units(
                candidate,
                claim_registry=registry,
                now=env.clock.now(),
                run_id=run.run_id,
                repair_attempt=attempt,
            )
            if result.valid:
                run = self._transition(run, Sig.VALIDATION_PASSED)
                syllabus = candidate
                break
            if result.next_action is NextAction.STRATEGIST_REPAIR_RETRY:
                run = self._transition(run, Sig.VALIDATION_FAILED_REPAIRABLE)
                continue
            run = self._transition(
                run, Sig.REPAIR_LIMIT_EXCEEDED, reason_code=result.reason_code
            )
            return self._propose_failure(
                run,
                explanation=env.nodes.explanation.run(
                    run_id=run.run_id, validation_result=result
                ),
            )
        if syllabus is None:
            raise CycleError("strategist repair loop ended without a terminal outcome")

        env.state.save_syllabus(onboarding.user_id, syllabus)
        bound_syllabus = syllabus

        def planner_pass(run_id: str, repair: ValidationResult | None) -> TaskPlan:
            return env.nodes.planner.run(
                run_id=run_id,
                syllabus=bound_syllabus,
                user_profile=onboarding.user_profile,
                repair=repair,
            )

        return self._plan_pipeline(
            run,
            onboarding=onboarding,
            syllabus=syllabus,
            make_plan=planner_pass,
            free_busy=free_busy,
            horizon_days=horizon_days,
            parent_plan_version=None,
            history_note="fresh propose",
        )

    def _propose_replan(
        self,
        onboarding: OnboardingRecord,
        run: RunRecord,
        *,
        recovery_mode: RecoveryAction | None,
        free_busy: Sequence[Mapping[str, Any]],
        horizon_days: int,
    ) -> ProposeResult:
        env = self._env
        active = env.plan_store.get_active(onboarding.user_id)
        if active is None:
            raise CycleError("replan required but no plan is active")
        syllabus = env.state.get_syllabus(onboarding.user_id)
        if syllabus is None:
            raise CycleError("replan required but no validated syllabus is stored")

        kind = run.replan_kind or ReplanKind.RECOVERY
        mode = run.recovery_mode or recovery_mode
        if kind is ReplanKind.RECOVERY and mode is None:
            raise CycleError(
                "recovery mode is ask_each_time: pass --recovery-mode "
                "(reschedule | scope_reduction | extend_timeline)"
            )

        run = self._transition(run, Sig.REPLAN_STARTED, recovery_mode=mode)
        make_plan = self._replan_plan_source(onboarding, active, syllabus, kind, mode)
        return self._plan_pipeline(
            run,
            onboarding=onboarding,
            syllabus=syllabus,
            make_plan=make_plan,
            free_busy=free_busy,
            horizon_days=horizon_days,
            parent_plan_version=active.plan_version,
            history_note=(
                f"replan ({kind.value}, mode={mode.value if mode else 'n/a'})"
            ),
        )

    def _replan_plan_source(
        self,
        onboarding: OnboardingRecord,
        active: PlanVersion,
        syllabus: SyllabusUnits,
        kind: ReplanKind,
        mode: RecoveryAction | None,
    ) -> Callable[[str, ValidationResult | None], TaskPlan]:
        """Pick where the replanned content comes from.

        Deterministic drafts (recalibration, reschedule) return constant plan
        content — they still pass full validation downstream, and they ignore
        the repair context (a constant cannot self-correct; the bounded loop
        exhausts into ``ERROR_REQUIRES_USER`` as before). Content-shaping
        modes route back through the Planner node — with the user's profile
        constraints and any failed ``ValidationResult`` — because
        deterministic code must not invent plan content (recovery spec
        "Choice Semantics").
        """
        env = self._env
        if kind is ReplanKind.RECALIBRATION:
            recalibrated = self._recalibrated_plan(onboarding, active)
            if recalibrated is not None:
                return lambda run_id, repair: recalibrated
            # Telemetry no longer moves any duration; fall back to the
            # deterministic reschedule draft so the run still converges.
            mode = RecoveryAction.RESCHEDULE
        if mode is None:
            raise CycleError("recovery replan requires a mode")
        proposal = propose_recovery_plan(
            active, mode, id_generator=env.id_generator, clock=env.clock
        )
        if proposal.route is RecoveryRoute.DETERMINISTIC_DRAFT:
            if proposal.draft is None:
                raise CycleError("deterministic recovery proposal carried no draft")
            deterministic_plan = proposal.draft.plan
            return lambda run_id, repair: deterministic_plan
        return lambda run_id, repair: env.nodes.planner.run(
            run_id=run_id,
            syllabus=syllabus,
            user_profile=onboarding.user_profile,
            repair=repair,
        )

    def _recalibrated_plan(
        self, onboarding: OnboardingRecord, active: PlanVersion
    ) -> TaskPlan | None:
        """Duration-recalibrated plan content, or ``None`` if nothing moves.

        The consent gate is checked for pooled serving on every resolution:
        without a granted scope the pooled tier is skipped with the typed
        denial reason and the user's own calibration (their data, no consent
        needed) still applies. The gate writes its audit entry either way.
        """
        env = self._env
        now = env.clock.now()
        events = self._events_for_plan(active.plan)
        categories = sorted(
            {t.category for t in active.plan.tasks}, key=lambda c: c.value
        )
        per_user = calibrate(
            events,
            {t.task_id: t.category for t in active.plan.tasks},
            user_id=onboarding.user_id,
            now=now,
            config=env.tuning.calibration,
        )
        gate_decision = env.consent_gate.check(
            onboarding.user_id,
            DataAccessPurpose.POOLED_SERVING,
            DataAccessor.SERVING_PIPELINE,
        )
        multipliers, _resolutions = resolve_effective_multipliers(
            categories,
            user_id=onboarding.user_id,
            computed_at=now,
            experience_level=onboarding.user_profile.experience_level,
            recent_completion_rate=completion_rate(events),
            per_user=per_user,
            model=None,  # no pooled model exists in the solo MVP
            pooled_denial_reason=(
                None if gate_decision.allowed else gate_decision.reason_code
            ),
            config=env.tuning.pooled_serving,
        )
        proposal = propose_recalibrated_plan(
            active, multipliers, id_generator=env.id_generator, clock=env.clock
        )
        return None if proposal is None else proposal.draft.plan

    def _plan_pipeline(
        self,
        run: RunRecord,
        *,
        onboarding: OnboardingRecord,
        syllabus: SyllabusUnits,
        make_plan: Callable[[str, ValidationResult | None], TaskPlan],
        free_busy: Sequence[Mapping[str, Any]],
        horizon_days: int,
        parent_plan_version: str | None,
        history_note: str,
    ) -> ProposeResult:
        """Planner → validation → scheduler with both bounded loops.

        ``make_plan`` is invoked once per planner pass — an LLM node for
        generated content, or a constant for deterministic recovery drafts
        (which then still pass full validation: no invalid plan reaches the
        Scheduler, whoever authored it). The second argument is the failed
        ``ValidationResult`` from the previous pass (``None`` on the first),
        so a repair retry (axiom 04: at most two) carries the typed
        violations back to the producer instead of re-invoking it blind.
        """
        env = self._env
        profile = onboarding.user_profile

        scheduler_iterations = 0
        while True:
            # --- planner stage (state: PLANNER_RUNNING) ---
            plan: TaskPlan | None = None
            repair: ValidationResult | None = None
            for attempt in range(MAX_REPAIR_ATTEMPTS_LLM + 1):
                try:
                    candidate = make_plan(run.run_id, repair)
                except LLMNodeError as exc:
                    return self._propose_failure(self._llm_failure(run, exc))
                run = self._transition(run, Sig.PLANNER_OUTPUT_PRODUCED)
                result = validate_task_plan(
                    candidate,
                    syllabus=syllabus,
                    user_profile=profile,
                    run_id=run.run_id,
                    repair_attempt=attempt,
                )
                if result.valid:
                    run = self._transition(run, Sig.VALIDATION_PASSED)
                    plan = candidate
                    break
                if result.next_action is NextAction.PLANNER_REPAIR_RETRY:
                    run = self._transition(run, Sig.VALIDATION_FAILED_REPAIRABLE)
                    repair = result
                    continue
                run = self._transition(
                    run, Sig.REPAIR_LIMIT_EXCEEDED, reason_code=result.reason_code
                )
                return self._propose_failure(
                    run,
                    explanation=env.nodes.explanation.run(
                        run_id=run.run_id, validation_result=result
                    ),
                )
            if plan is None:
                raise CycleError("planner repair loop ended without a terminal outcome")

            # --- scheduler stage (state: SCHEDULER_RUNNING) ---
            plan_version_id = env.id_generator.new_id("plan")
            versioned_plan = TaskPlan.model_validate(
                plan.model_dump() | {"plan_version": plan_version_id}
            )
            # Anchor the horizon in the user's local timezone so the scheduler
            # reads the time-of-day constraints (no_events_before/after and the
            # deep-work windows) as *local* times, not UTC. The placed entries
            # stay timezone-aware and convert to the correct instant on write.
            horizon_start = env.clock.now().astimezone(onboarding.tzinfo())
            output = schedule(
                SchedulerInput(
                    run_id=run.run_id,
                    plan_version=plan_version_id,
                    plan=versioned_plan,
                    policy=policy_from_user_profile(profile),
                    calendar_free_busy=[
                        FreeBusyInterval.model_validate(dict(fb)) for fb in free_busy
                    ],
                    horizon_start=horizon_start,
                    horizon_end=horizon_start + timedelta(days=horizon_days),
                )
            )
            if output.schedule_status is ScheduleStatus.SUCCESS:
                run = self._transition(run, Sig.SCHEDULER_SUCCESS)
                return self._finish_propose(
                    run,
                    onboarding=onboarding,
                    plan=versioned_plan,
                    output=output,
                    parent_plan_version=parent_plan_version,
                    history_note=history_note,
                )
            scheduler_iterations += 1
            if scheduler_iterations >= MAX_SCHEDULER_PLANNER_ITERATIONS:
                reason = (
                    output.unscheduled_tasks[0].reason_code
                    if output.unscheduled_tasks
                    else ReasonCode.INSUFFICIENT_WEEKLY_CAPACITY
                )
                run = self._transition(run, Sig.REPAIR_LIMIT_EXCEEDED, reason_code=reason)
                return self._propose_failure(run, output=output)
            signal = (
                Sig.SCHEDULER_PARTIAL_FAILURE
                if output.schedule_status is ScheduleStatus.PARTIAL_FAILURE
                else Sig.SCHEDULER_FULL_FAILURE
            )
            run = self._transition(run, signal)

    def _finish_propose(
        self,
        run: RunRecord,
        *,
        onboarding: OnboardingRecord,
        plan: TaskPlan,
        output: SchedulerOutput,
        parent_plan_version: str | None,
        history_note: str,
    ) -> ProposeResult:
        env = self._env
        now = env.clock.now()
        history = [
            GenerationStepRecord(step=step, occurred_at=now, detail=history_note)
            for step in (
                GenerationStep.PLANNER,
                GenerationStep.VALIDATION,
                GenerationStep.SCHEDULER,
            )
        ]
        plan_version = PlanVersion(
            plan_version=plan.plan_version,
            user_id=onboarding.user_id,
            parent_plan_version=parent_plan_version,
            state=LifecycleState.DRAFT,
            plan=plan,
            generation_history=history,
            created_at=now,
            updated_at=now,
        )
        env.plan_store.save(plan_version)

        draft = DraftSchedule.from_scheduler_output(
            output,
            draft_schedule_id=env.id_generator.new_id("draft"),
            created_at=now,
        )
        env.state.save_draft(onboarding.user_id, draft)
        run = self._save_run(
            run,
            plan_version=plan.plan_version,
            draft_schedule_id=draft.draft_schedule_id,
            reason_code=None,
        )
        return ProposeResult(
            run_id=run.run_id,
            user_id=run.user_id,
            state=run.state,
            plan_version=plan.plan_version,
            parent_plan_version=parent_plan_version,
            replan_kind=run.replan_kind,
            recovery_mode=run.recovery_mode,
            draft_schedule_id=draft.draft_schedule_id,
            draft_payload_hash=canonical_payload_hash(
                draft, HASH_CANONICALIZATION_VERSION
            ),
            scheduled_task_count=len(output.scheduled_tasks),
            unscheduled_tasks=list(output.unscheduled_tasks),
            repair_options=list(output.repair_options),
        )

    def _llm_failure(self, run: RunRecord, exc: LLMNodeError) -> RunRecord:
        """Typed panic: an LLM node failed beyond its bounded internal retries."""
        reason = getattr(exc, "reason_code", None) or ReasonCode.LLM_CALL_FAILED
        return self._transition(run, Sig.UNRECOVERABLE_ERROR, reason_code=reason)

    def _propose_failure(
        self,
        run: RunRecord,
        *,
        explanation: UserExplanation | None = None,
        output: SchedulerOutput | None = None,
    ) -> ProposeResult:
        return ProposeResult(
            run_id=run.run_id,
            user_id=run.user_id,
            state=run.state,
            reason_code=run.reason_code,
            replan_kind=run.replan_kind,
            recovery_mode=run.recovery_mode,
            unscheduled_tasks=list(output.unscheduled_tasks) if output else [],
            repair_options=list(output.repair_options) if output else [],
            explanation=explanation,
        )

    # ------------------------------------------------------------------ #
    # approve
    # ------------------------------------------------------------------ #

    def approve(
        self,
        user_id: str,
        *,
        run_id: str | None = None,
        reject: bool = False,
        ttl: timedelta = DEFAULT_APPROVAL_TTL,
    ) -> ApproveResult:
        """Record the user's explicit decision on the awaiting draft."""
        env = self._env
        run = self._require_run(user_id, run_id, expected=S.AWAITING_USER_APPROVAL)
        if run.plan_version is None or run.draft_schedule_id is None:
            raise CycleError("run is awaiting approval but has no draft attached")
        draft_schedule_id = run.draft_schedule_id
        plan_version = env.plan_store.get(user_id, run.plan_version)

        if reject:
            env.plan_store.save(
                plan_version.transition_to(LifecycleState.DISCARDED, now=env.clock.now())
            )
            run = self._transition(run, Sig.USER_REJECTED)
            return ApproveResult(
                run_id=run.run_id,
                user_id=user_id,
                state=run.state,
                rejected=True,
                plan_version=plan_version.plan_version,
            )

        draft = env.state.get_draft(draft_schedule_id)
        if draft is None:
            raise CycleError(f"draft {draft_schedule_id!r} not found")
        now = env.clock.now()
        approved_hash = canonical_payload_hash(draft, HASH_CANONICALIZATION_VERSION)
        approval = ApprovalEvent(
            approval_event_id=env.id_generator.new_id("approval"),
            user_id=user_id,
            plan_id=plan_version.plan_version,
            draft_schedule_id=draft.draft_schedule_id,
            action_type=ApprovalActionType.ADD_TO_CALENDAR,
            approved_payload_hash=approved_hash,
            hash_algorithm=HashAlgorithm.SHA256,
            hash_canonicalization_version=HASH_CANONICALIZATION_VERSION,
            created_at=now,
            expires_at=now + ttl,
        )
        env.approval_store.save(approval)
        env.plan_store.save(plan_version.transition_to(LifecycleState.APPROVED, now=now))
        run = self._transition(
            run, Sig.USER_APPROVED, approval_event_id=approval.approval_event_id
        )
        return ApproveResult(
            run_id=run.run_id,
            user_id=user_id,
            state=run.state,
            rejected=False,
            plan_version=plan_version.plan_version,
            approval_event_id=approval.approval_event_id,
            approved_payload_hash=approved_hash,
            expires_at_iso=approval.expires_at.isoformat(),
        )

    # ------------------------------------------------------------------ #
    # adjust (drag-to-adjust, pre-approval)
    # ------------------------------------------------------------------ #

    def adjust(
        self,
        user_id: str,
        adjustments: Sequence[DraftAdjustment],
        *,
        run_id: str | None = None,
        free_busy: Sequence[Mapping[str, Any]] = (),
    ) -> AdjustResult:
        """Reposition proposed blocks on the awaiting draft, server-validated.

        The user's drag edits (``adjustments``: ``task_id`` → new start) are
        applied to the pending draft with each block's duration preserved, then
        the WHOLE resulting placement is re-validated against the user's policy
        and ``free_busy`` — never the client's own conflict checks. A clean move
        replaces the pending draft with a new immutable one and returns its fresh
        canonical hash; a rejected move persists nothing and returns the typed
        ``violations``.

        Valid only while the run awaits approval: the state guard refuses a move
        once the draft is approved, so re-approval (not silent mutation) is the
        contract, and axiom 06's write-time hash recheck still validates exactly
        what the user approved.
        """
        env = self._env
        if not adjustments:
            raise CycleError("no adjustments supplied")
        task_ids = [adjustment.task_id for adjustment in adjustments]
        if len(task_ids) != len(set(task_ids)):
            raise CycleError("adjustments contain a duplicate task_id")

        onboarding = self._require_onboarding(user_id)
        run = self._require_run(user_id, run_id, expected=S.AWAITING_USER_APPROVAL)
        if run.draft_schedule_id is None or run.plan_version is None:
            raise CycleError("run is awaiting approval but has no draft/plan attached")
        draft = env.state.get_draft(run.draft_schedule_id)
        if draft is None:
            raise CycleError(f"draft {run.draft_schedule_id!r} not found")
        plan_version = env.plan_store.get(user_id, run.plan_version)

        tz = onboarding.tzinfo()
        new_starts = {
            adjustment.task_id: adjustment.start.astimezone(tz)
            for adjustment in adjustments
        }
        try:
            candidate = draft.with_adjustments(
                new_starts,
                draft_schedule_id=env.id_generator.new_id("draft"),
                created_at=env.clock.now(),
            )
        except ValueError as exc:
            # Unknown task_id: the client tried to move a task not in the draft.
            raise CycleError(str(exc)) from exc

        conflicts = validate_placements(
            candidate.entries,
            plan=plan_version.plan,
            policy=policy_from_user_profile(onboarding.user_profile),
            free_busy=[FreeBusyInterval.model_validate(dict(fb)) for fb in free_busy],
            tz=tz,
        )
        if conflicts:
            return AdjustResult(
                run_id=run.run_id,
                user_id=user_id,
                state=run.state,
                applied=False,
                reason_code=conflicts[0].reason_code,
                violations=[
                    AdjustViolation(
                        task_id=conflict.task_id,
                        reason_code=conflict.reason_code,
                        detail=conflict.detail,
                    )
                    for conflict in conflicts
                ],
            )

        env.state.save_draft(user_id, candidate)
        # Pure artifact swap: the run stays in AWAITING_USER_APPROVAL (no
        # lifecycle transition) — only the pending draft it points at changes.
        run = self._save_run(run, draft_schedule_id=candidate.draft_schedule_id)
        return AdjustResult(
            run_id=run.run_id,
            user_id=user_id,
            state=run.state,
            applied=True,
            draft_schedule_id=candidate.draft_schedule_id,
            draft_payload_hash=canonical_payload_hash(
                candidate, HASH_CANONICALIZATION_VERSION
            ),
            adjusted_task_ids=sorted(new_starts),
            scheduled_task_count=len(candidate.entries),
        )

    # ------------------------------------------------------------------ #
    # write
    # ------------------------------------------------------------------ #

    def write(
        self,
        user_id: str,
        *,
        run_id: str | None = None,
        target_calendar_id: str = DEFAULT_TARGET_CALENDAR_ID,
        dry_run: bool = False,
    ) -> WriteCycleResult:
        """Execute (or dry-run) the approved calendar write.

        All axiom 06 machinery — hash recheck, lock, duplicate guard,
        verification read-back — lives in ``CalendarWriteManager``; this
        method only sequences supervisor transitions around it and activates
        the plan version after a verified write.

        The manager already translates every ``CalendarWriterError`` into a
        typed ``WriteResult`` at its boundary; the ``AgenticCalendarError``
        guard around it is defense in depth so no adapter/manager defect can
        ever escape the operator surface raw and strand a run in
        ``CALENDAR_WRITE_IN_PROGRESS`` — every failure leaves the run in a
        typed terminal state with a ``reason_code`` (axiom 16).
        """
        env = self._env
        run = self._require_run(user_id, run_id, expected=S.CALENDAR_WRITE_APPROVED)
        if run.approval_event_id is None or run.draft_schedule_id is None:
            raise CycleError("run is approved but missing approval/draft identifiers")
        approval_event_id = run.approval_event_id
        draft = env.state.get_draft(run.draft_schedule_id)
        if draft is None:
            raise CycleError(f"draft {run.draft_schedule_id!r} not found")

        if dry_run:
            preview = env.write_manager.preview(
                draft=draft, target_calendar_id=target_calendar_id
            )
            return WriteCycleResult(
                run_id=run.run_id,
                user_id=user_id,
                state=run.state,
                dry_run=True,
                planned_event_count=len(preview.planned_events),
            )

        run = self._transition(run, Sig.CALENDAR_WRITE_STARTED)
        try:
            result = env.write_manager.approve_and_write(
                approval_event_id=approval_event_id,
                draft=draft,
                target_calendar_id=target_calendar_id,
            )
        except AgenticCalendarError as exc:
            reason: ReasonCode = (
                getattr(exc, "reason_code", None) or ReasonCode.CALENDAR_WRITE_FAILED
            )
            run = self._transition(
                run, Sig.CALENDAR_WRITE_FAILED, reason_code=reason
            )
            return WriteCycleResult(
                run_id=run.run_id,
                user_id=user_id,
                state=run.state,
                dry_run=False,
                write_status="failed",
                reason_code=run.reason_code,
                written_task_ids=[],
                verified_task_ids=[],
                failed_task_ids=[],
                mapping_status_by_task={},
                # Operator diagnosability: domain-error messages are typed
                # prose (never raw calendar content or secrets), so the text
                # is safe to surface alongside the reason_code.
                error=str(exc),
            )
        verified = (
            result.status is WriteStatus.SUCCESS
            and result.verification is not None
            and result.verification.all_verified
        )
        if verified:
            run = self._transition(run, Sig.CALENDAR_WRITE_SUCCEEDED)
            self._activate_plan(user_id, run)
            run = self._transition(run, Sig.PLAN_ACTIVATED)
        elif result.status is WriteStatus.SUCCESS:
            run = self._transition(
                run,
                Sig.CALENDAR_VERIFICATION_FAILED,
                reason_code=ReasonCode.CALENDAR_VERIFICATION_FAILED,
            )
        else:
            run = self._transition(
                run, Sig.CALENDAR_WRITE_FAILED, reason_code=result.reason_code
            )

        mappings = (
            env.mapping_store.list_for_run(result.run_id)
            if result.run_id is not None
            else []
        )
        verification = result.verification
        return WriteCycleResult(
            run_id=run.run_id,
            user_id=user_id,
            state=run.state,
            dry_run=False,
            write_status=result.status.value,
            reason_code=run.reason_code,
            written_task_ids=[m.task_id for m in result.written_mappings],
            verified_task_ids=(
                list(verification.verified_task_ids) if verification else []
            ),
            failed_task_ids=list(verification.failed_task_ids) if verification else [],
            mapping_status_by_task={
                m.task_id: m.calendar_write_status.value for m in mappings
            },
            # The manager's translated failure detail (e.g. the Google
            # adapter's enriched "events.list failed ...: HTTP 403" prose);
            # None on success.
            error=result.error,
        )

    def _activate_plan(self, user_id: str, run: RunRecord) -> None:
        """APPROVED → ACTIVE, discarding any previously active plan first.

        The plan store enforces single-active; a replan supersedes its parent,
        so the prior active version is explicitly discarded — never silently
        overwritten (plan versions are immutable history).
        """
        env = self._env
        if run.plan_version is None:
            raise CycleError("cannot activate: run carries no plan version")
        now = env.clock.now()
        prior = env.plan_store.get_active(user_id)
        if prior is not None and prior.plan_version != run.plan_version:
            env.plan_store.save(prior.transition_to(LifecycleState.DISCARDED, now=now))
        approved = env.plan_store.get(user_id, run.plan_version)
        env.plan_store.save(approved.transition_to(LifecycleState.ACTIVE, now=now))

    # ------------------------------------------------------------------ #
    # ingest
    # ------------------------------------------------------------------ #

    def ingest(self, user_id: str, payloads: Sequence[Mapping[str, Any]]) -> IngestResult:
        """Store telemetry, then deterministically assess the active plan.

        Assessment = drift classification (+ reflection prose), accountability
        evaluation (nudge / recommitment side effects through their audited
        services), and the replan decision. A required replan parks the run in
        ``REPLAN_REQUIRED`` — generating the new proposal is ``propose``'s
        job, and writing anything remains behind approve + write.
        """
        env = self._env
        onboarding = self._require_onboarding(user_id)
        outcomes = [env.telemetry_ingestor.ingest(p) for p in payloads]
        items = [
            TelemetryItemOutcome(
                status=o.status.value,
                telemetry_event_id=o.event.telemetry_event_id if o.event else None,
                reason_code=o.reason_code,
                error=o.error,
            )
            for o in outcomes
        ]
        base_fields: dict[str, Any] = {
            "user_id": user_id,
            "outcomes": items,
            "ingested_count": sum(1 for o in items if o.status == "ingested"),
            "duplicate_count": sum(1 for o in items if o.status == "duplicate"),
            "rejected_count": sum(1 for o in items if o.status == "rejected"),
        }

        run = env.state.latest_run_for_user(user_id)
        active = env.plan_store.get_active(user_id)
        if run is None or run.state is not S.ACTIVE_PLAN or active is None:
            return IngestResult(
                **base_fields,
                run_id=run.run_id if run else None,
                state=run.state if run else None,
            )

        plan = active.plan
        events = self._events_for_plan(plan)

        # Plan completion ends the journey (axiom 02 terminal success).
        completed_ids = {e.task_id for e in events if e.completed}
        if completed_ids >= {t.task_id for t in plan.tasks}:
            run = self._transition(run, Sig.PLAN_COMPLETED)
            return IngestResult(
                **base_fields,
                run_id=run.run_id,
                state=run.state,
                assessed=True,
                plan_completed=True,
            )

        drift_events = env.drift_classifier.classify(
            DriftInput(plan=plan, events=events)
        )
        reflection = (
            env.nodes.reflection.run(
                run_id=run.run_id,
                drift_events=drift_events,
                completion_rate=completion_rate(events) if events else None,
            )
            if drift_events
            else None
        )

        acc = self._evaluate_accountability(onboarding, run, active, events)
        decision = acc.outcome.decision if acc.outcome is not None else None
        replan = self._replan_decision(onboarding, active, drift_events, acc.outcome)

        if not drift_events:
            run = self._transition(run, Sig.NO_DRIFT)
        else:
            run = self._transition(run, Sig.DRIFT_DETECTED)
            if replan.required:
                run = self._transition(
                    run,
                    Sig.REPLAN_REQUIRED,
                    replan_kind=replan.kind,
                    recovery_mode=replan.mode,
                    reason_code=replan.reason_code,
                )
            else:
                run = self._transition(run, Sig.REPLAN_NOT_REQUIRED)

        return IngestResult(
            **base_fields,
            run_id=run.run_id,
            state=run.state,
            assessed=True,
            drift_events=list(drift_events),
            reflection=reflection,
            accountability_action=(
                decision.action.value if decision and decision.action else None
            ),
            accountability_reason_code=decision.reason_code if decision else None,
            nudge_id=acc.nudge_id,
            recommitment_request_id=acc.recommitment_request_id,
            replan_required=replan.required,
            replan_kind=replan.kind,
            recovery_mode=replan.mode,
            recovery_mode_pending_user_choice=replan.pending_user_choice,
        )

    def _evaluate_accountability(
        self,
        onboarding: OnboardingRecord,
        run: RunRecord,
        active: PlanVersion,
        events: Sequence[TelemetryEvent],
    ) -> _AccountabilityPass:
        """One accountability pass (opt-in: requires a motivation profile)."""
        env = self._env
        mp = onboarding.motivation_profile
        if mp is None:
            return _AccountabilityPass(None, None, None)
        now = env.clock.now()
        tz = onboarding.tzinfo()
        contract = derive_accountability_contract(
            mp, id_generator=env.id_generator, clock=env.clock
        )
        checkins = env.checkin_store.list_for_plan(onboarding.user_id, active.plan_version)
        checkin = evaluate_checkin(contract, checkins, now=now, tz=tz)
        scheduled_due, completed_due, events_7d, events_14d = self._projection_windows(
            run, active, events, now
        )
        outcome = evaluate_accountability(
            ProjectionInput(
                user_id=onboarding.user_id,
                plan_id=active.plan_version,
                events_7d=events_7d,
                events_14d=events_14d,
                scheduled_minutes_due=scheduled_due,
                completed_minutes_due=completed_due,
            ),
            contract,
            checkin.status,
            clock=env.clock,
            id_generator=env.id_generator,
        )
        nudge = env.nudge_service.maybe_deliver(
            decision=outcome.decision, contract=contract, tz=tz
        )
        recommitment_id: str | None = None
        if outcome.decision.action is AccountabilityAction.SEND_USER_NUDGE:
            request = request_recommitment(
                outcome.decision,
                plan_version=active.plan_version,
                store=env.recommitment_store,
                clock=env.clock,
                id_generator=env.id_generator,
            )
            recommitment_id = request.recommitment_request_id
        return _AccountabilityPass(
            outcome, nudge.nudge_id if nudge else None, recommitment_id
        )

    def accountability_snapshot(self, user_id: str) -> AccountabilitySnapshot | None:
        """Read-only accountability projection for the dashboard.

        Mirrors the *pure* half of :meth:`_evaluate_accountability` — derive
        the contract, evaluate the weekly check-in, project the windows, and
        decide — but STOPS before every side effect that method performs: no
        nudge delivery, no recommitment request, no run-state transition.
        Performs no transitions and no writes, exactly like :meth:`status`.

        Returns ``None`` when accountability cannot be projected: the user is
        not onboarded, has no active plan or run yet, or — the opt-in gate of
        axiom 21, the same early-return as ``_evaluate_accountability`` — has
        no motivation profile.
        """
        env = self._env
        onboarding = env.state.get_onboarding(user_id)
        if onboarding is None or onboarding.motivation_profile is None:
            return None
        active = env.plan_store.get_active(user_id)
        run = env.state.latest_run_for_user(user_id)
        if active is None or run is None:
            return None
        now = env.clock.now()
        tz = onboarding.tzinfo()
        contract = derive_accountability_contract(
            onboarding.motivation_profile, id_generator=env.id_generator, clock=env.clock
        )
        checkins = env.checkin_store.list_for_plan(user_id, active.plan_version)
        checkin = evaluate_checkin(contract, checkins, now=now, tz=tz)
        events = self._events_for_plan(active.plan)
        scheduled_due, completed_due, events_7d, events_14d = self._projection_windows(
            run, active, events, now
        )
        outcome = evaluate_accountability(
            ProjectionInput(
                user_id=user_id,
                plan_id=active.plan_version,
                events_7d=events_7d,
                events_14d=events_14d,
                scheduled_minutes_due=scheduled_due,
                completed_minutes_due=completed_due,
            ),
            contract,
            checkin.status,
            clock=env.clock,
            id_generator=env.id_generator,
        )
        return AccountabilitySnapshot(
            checkin_status=checkin.status, state=outcome.state, decision=outcome.decision
        )

    def _projection_windows(
        self,
        run: RunRecord,
        active: PlanVersion,
        events: Sequence[TelemetryEvent],
        now: datetime,
    ) -> tuple[int, int, list[TelemetryEvent], list[TelemetryEvent]]:
        """Caller-scoped projection inputs from the active draft schedule.

        A task is "due" when its draft entry has ended; the windows scope
        telemetry by that scheduled end (the observable plan position), not
        by when the user happened to report it.
        """
        env = self._env
        entries: tuple[Any, ...] = ()
        if run.draft_schedule_id is not None:
            draft = env.state.get_draft(run.draft_schedule_id)
            if draft is not None:
                entries = draft.entries
        end_by_task = {e.task_id: e.end for e in entries}
        durations = {t.task_id: t.estimated_duration_min for t in active.plan.tasks}

        due_ids = {tid for tid, end in end_by_task.items() if end <= now}
        scheduled_due = sum(durations.get(tid, 0) for tid in due_ids)
        completed_due = sum(
            (e.actual_duration_min or e.scheduled_duration_min)
            for e in events
            if e.completed and e.task_id in due_ids
        )

        def window(days: int) -> list[TelemetryEvent]:
            cutoff = now - timedelta(days=days)
            return [
                e
                for e in events
                if e.task_id in due_ids and cutoff <= end_by_task[e.task_id] <= now
            ]

        return scheduled_due, completed_due, window(7), window(14)

    def _replan_decision(
        self,
        onboarding: OnboardingRecord,
        active: PlanVersion,
        drift_events: Sequence[DriftEvent],
        outcome: AccountabilityOutcome | None,
    ) -> _ReplanDecision:
        """Deterministic replan verdict with fixed precedence.

        1. An accountability ``GENERATE_RECOVERY_PLAN_DRAFT`` decision wins:
           mode comes from the motivation profile's recovery preference, or
           is left for the user when it is ``ask_each_time``.
        2. Duration drift next: if recalibration would actually move a
           duration, a recalibration replan is required.
        3. Otherwise the first drift event (classifier's canonical order)
           whose recommended action maps to a recovery mode decides.

        The replan itself only fires when drift was detected — the supervisor
        has no ``ACTIVE_PLAN → REPLAN_REQUIRED`` edge without it.
        """
        if (
            outcome is not None
            and outcome.decision.action
            is AccountabilityAction.GENERATE_RECOVERY_PLAN_DRAFT
            and onboarding.motivation_profile is not None
        ):
            preference = onboarding.motivation_profile.recovery_mode_preference
            if preference is RecoveryPreference.ASK_EACH_TIME:
                return _ReplanDecision(
                    ReplanKind.RECOVERY, None, True, outcome.decision.reason_code
                )
            return _ReplanDecision(
                ReplanKind.RECOVERY,
                RecoveryAction(preference.value),
                False,
                outcome.decision.reason_code,
            )

        duration_drift = [
            e
            for e in drift_events
            if e.recommended_policy_action
            in (
                RecommendedPolicyAction.INCREASE_DURATION_ESTIMATES_FOR_CATEGORY,
                RecommendedPolicyAction.DECREASE_DURATION_ESTIMATES_FOR_CATEGORY,
            )
        ]
        if duration_drift and self._recalibrated_plan(onboarding, active) is not None:
            return _ReplanDecision(
                ReplanKind.RECALIBRATION, None, False, duration_drift[0].reason_code
            )

        for event in drift_events:
            mode = DRIFT_ACTION_TO_RECOVERY_MODE.get(event.recommended_policy_action)
            if mode is not None:
                return _ReplanDecision(
                    ReplanKind.RECOVERY, mode, False, event.reason_code
                )
        return _ReplanDecision(None, None, False, None)

    def _events_for_plan(self, plan: TaskPlan) -> list[TelemetryEvent]:
        env = self._env
        events: list[TelemetryEvent] = []
        for task in plan.tasks:
            events.extend(env.telemetry_store.list_for_task(task.task_id))
        return events

    # ------------------------------------------------------------------ #
    # status
    # ------------------------------------------------------------------ #

    def status(self, user_id: str) -> StatusResult:
        """Read-only snapshot; performs no transitions and no side effects."""
        env = self._env
        onboarding = env.state.get_onboarding(user_id)
        run = env.state.latest_run_for_user(user_id)
        active = env.plan_store.get_active(user_id) if onboarding else None
        plan_versions = env.plan_store.list_for_user(user_id) if onboarding else []

        # Calendar mappings are keyed by the write manager's own run_id;
        # surface the latest status per task of the active plan instead.
        mapping_status: dict[str, str] = {}
        if active is not None:
            for task in active.plan.tasks:
                task_mappings = env.mapping_store.list_for_task(task.task_id)
                if task_mappings:
                    mapping_status[task.task_id] = (
                        task_mappings[-1].calendar_write_status.value
                    )
        return StatusResult(
            user_id=user_id,
            onboarded=onboarding is not None,
            timezone=onboarding.timezone if onboarding else None,
            run_id=run.run_id if run else None,
            state=run.state if run else None,
            reason_code=run.reason_code if run else None,
            plan_version=run.plan_version if run else None,
            active_plan_version=active.plan_version if active else None,
            plan_version_count=len(plan_versions),
            draft_schedule_id=run.draft_schedule_id if run else None,
            approval_event_id=run.approval_event_id if run else None,
            replan_kind=run.replan_kind if run else None,
            recovery_mode=run.recovery_mode if run else None,
            mapping_status_by_task=mapping_status,
            telemetry_event_count=len(env.telemetry_store.all()),
            nudge_count=len(env.nudge_store.list_for_user(user_id)),
            checkin_count=len(env.checkin_store.all()),
        )

    # ------------------------------------------------------------------ #
    # Read projections (F-A): JSON the SPA renders from. All read-only and
    # side-effect-free, deriving from the same stores the operator surfaces
    # use. ``checkin`` is the one mutation here — it shares ``ingest`` but
    # enforces the membership / due / idempotency guard the client cannot.
    # ------------------------------------------------------------------ #

    def _active_draft(self, user_id: str) -> DraftSchedule | None:
        """The draft backing the user's *active* (written) plan, or ``None``.

        Guards that the latest run's draft matches the active plan version, so a
        replan-in-flight draft is never shown as today's schedule.
        """
        env = self._env
        run = env.state.latest_run_for_user(user_id)
        active = env.plan_store.get_active(user_id)
        if active is None or run is None or run.draft_schedule_id is None:
            return None
        draft = env.state.get_draft(run.draft_schedule_id)
        if draft is None or draft.plan_version != active.plan_version:
            return None
        return draft

    def draft_view(
        self, user_id: str, *, free_busy: Sequence[Mapping[str, str]] | None = None
    ) -> DraftView:
        """The pending draft + its canonical hash for the review/approval
        screens. ``free_busy`` (the imported busy windows the grid draws as
        fixed) is fetched by the web layer and passed through."""
        env = self._env
        run = env.state.latest_run_for_user(user_id)
        draft: DraftSchedule | None = None
        payload_hash: str | None = None
        task_titles: dict[str, str] = {}
        if run is not None and run.draft_schedule_id is not None:
            draft = env.state.get_draft(run.draft_schedule_id)
            if draft is not None:
                payload_hash = canonical_payload_hash(draft, HASH_CANONICALIZATION_VERSION)
                plan = env.plan_store.get(user_id, draft.plan_version)
                if plan is not None:
                    task_titles = {task.task_id: task.title for task in plan.plan.tasks}
        return DraftView(
            draft=draft,
            payload_hash=payload_hash,
            hash_canonicalization_version=HASH_CANONICALIZATION_VERSION,
            free_busy=[dict(interval) for interval in (free_busy or [])],
            task_titles=task_titles,
        )

    def today(self, user_id: str) -> TodayResult:
        """The active plan's scheduled tasks as structured rows (tz-aware
        datetimes; the client localizes). ``due`` marks a block whose time has
        passed; ``reported`` marks one that already has telemetry."""
        env = self._env
        onboarding = env.state.get_onboarding(user_id)
        timezone = onboarding.timezone if onboarding is not None else None
        draft = self._active_draft(user_id)
        active = env.plan_store.get_active(user_id)
        if draft is None or active is None:
            return TodayResult(timezone=timezone, tasks=[])
        now = env.clock.now()
        tasks = {task.task_id: task for task in active.plan.tasks}
        rows: list[TodayTask] = []
        for entry in draft.entries:
            task = tasks.get(entry.task_id)
            if task is None:
                continue
            rows.append(
                TodayTask(
                    task_id=entry.task_id,
                    title=task.title,
                    category=task.category.value,
                    required_focus_level=task.required_focus_level.value,
                    start=entry.start,
                    end=entry.end,
                    due=entry.end <= now,
                    reported=bool(env.telemetry_store.list_for_task(entry.task_id)),
                )
            )
        return TodayResult(timezone=timezone, tasks=rows)

    def thresholds_view(self) -> ThresholdsResult:
        """Effective deterministic tuning the system serves + the append-only
        change journal. Compares each served value against the code default —
        the same honest projection the ``show_thresholds`` CLI prints."""
        env = self._env
        sections: list[ThresholdSectionView] = []
        for name, (config_type, default) in TUNABLE_SECTIONS.items():
            effective = getattr(env.tuning, name)
            fields: list[ThresholdFieldView] = []
            for field_name in scalar_fields(config_type):
                value = getattr(effective, field_name)
                default_value = getattr(default, field_name)
                fields.append(
                    ThresholdFieldView(
                        name=field_name,
                        value=value,
                        status="default" if value == default_value else "overridden",
                    )
                )
            sections.append(ThresholdSectionView(name=name, fields=fields))
        return ThresholdsResult(sections=sections, history=env.threshold_log_store.list_all())

    def me(self, user_id: str) -> MeResult:
        """Identity + saved profile for the wizard's prefill / edit-later."""
        env = self._env
        onboarding = env.state.get_onboarding(user_id)
        credential = env.credential_store.get_by_user(user_id)
        return MeResult(
            user_id=user_id,
            onboarded=onboarding is not None,
            timezone=onboarding.timezone if onboarding is not None else None,
            email=credential.email if credential is not None else None,
            profile=onboarding.user_profile if onboarding is not None else None,
        )

    def accountability_view(self, user_id: str) -> AccountabilityResult:
        """The read-only accountability projection plus whether the user has a
        motivation profile — so the dashboard distinguishes "not set up"
        (empty-state, axiom 21) from "no active plan yet"."""
        env = self._env
        onboarding = env.state.get_onboarding(user_id)
        has_motivation_profile = (
            onboarding is not None and onboarding.motivation_profile is not None
        )
        snapshot = self.accountability_snapshot(user_id)
        return AccountabilityResult(
            has_motivation_profile=has_motivation_profile,
            checkin_status=snapshot.checkin_status.value if snapshot is not None else None,
            state=snapshot.state if snapshot is not None else None,
            decision=snapshot.decision if snapshot is not None else None,
        )

    def checkin(self, user_id: str, task_id: str, *, completed: bool) -> IngestResult:
        """Report a scheduled block's outcome as completion telemetry.

        Server-authoritative guard the client cannot bypass: the task must be in
        the active schedule, its block must have ended (``due``), and it must not
        already be reported (idempotency — no double-count). A completion carries
        actuals + timestamp so ``data_quality`` stays ``complete``; a miss
        carries neither. Then it flows through the same :meth:`ingest` path the
        operator surface uses.
        """
        env = self._env
        draft = self._active_draft(user_id)
        entry = (
            next((e for e in draft.entries if e.task_id == task_id), None)
            if draft is not None
            else None
        )
        if entry is None:
            raise CycleError(f"task {task_id!r} is not in the active schedule")
        if entry.end > env.clock.now():
            raise CycleError(f"task {task_id!r} is not yet due")
        if env.telemetry_store.list_for_task(task_id):
            raise CycleError(f"task {task_id!r} has already been reported")
        scheduled_min = int((entry.end - entry.start).total_seconds() // 60)
        payload: dict[str, Any] = {
            "telemetry_event_id": env.id_generator.new_id("telemetry"),
            "task_id": task_id,
            "scheduled_duration_min": scheduled_min,
            "actual_duration_min": scheduled_min if completed else None,
            "completed": completed,
            "user_reschedule_count": 0,
            "data_quality": "complete",
        }
        if completed:
            payload["completion_timestamp"] = env.clock.now()
        return self.ingest(user_id, [payload])
