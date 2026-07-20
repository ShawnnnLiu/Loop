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
from datetime import date, datetime, time, timedelta
from typing import Any

from agentic_calendar.accountability.checkin import CheckinStatus, evaluate_checkin
from agentic_calendar.accountability.contract import derive_accountability_contract
from agentic_calendar.accountability.policy_engine import (
    AccountabilityOutcome,
    evaluate_accountability,
)
from agentic_calendar.accountability.projection import ProjectionInput
from agentic_calendar.accountability.recommitment import (
    RECOMMITMENT_CHOICE_TO_RECOVERY_MODE,
    record_recommitment,
    request_recommitment,
)
from agentic_calendar.calendar_writer.errors import CalendarWriterError
from agentic_calendar.calendar_writer.manager import WriteResult, WriteStatus
from agentic_calendar.common.errors import AgenticCalendarError
from agentic_calendar.common.logging import correlated, get_logger
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
from agentic_calendar.contracts.calendar_event_mapping import (
    CalendarEventMapping,
    CalendarWriteStatus,
)
from agentic_calendar.contracts.calendar_reconciliation import (
    CalendarEditType,
    CalendarEventDelta,
    CalendarReconciliationResult,
    ReconciliationDisposition,
    ReconciliationOutcome,
)
from agentic_calendar.contracts.career_track import CareerTrack
from agentic_calendar.contracts.checkin_event import CheckinEvent, RecoveryAction
from agentic_calendar.contracts.common_types import EvidenceKind, TaskCategory
from agentic_calendar.contracts.data_access_audit import (
    DataAccessor,
    DataAccessPurpose,
)
from agentic_calendar.contracts.draft_schedule import DraftSchedule, DraftScheduleEntry
from agentic_calendar.contracts.drift_event import DriftEvent, RecommendedPolicyAction
from agentic_calendar.contracts.hashing import canonical_payload_hash
from agentic_calendar.contracts.motivation_profile import RecoveryPreference
from agentic_calendar.contracts.notification_log import NotificationStatus
from agentic_calendar.contracts.pathway_selection import PathwaySelection
from agentic_calendar.contracts.pathway_template import PathwayTemplate
from agentic_calendar.contracts.placement_evidence import (
    EVIDENCE_MULTIPLIER_MAX,
    EVIDENCE_MULTIPLIER_MIN,
    EvidenceCell,
    EvidenceSource,
    PlacementEvidence,
)
from agentic_calendar.contracts.placement_preference import (
    PlacementPreferenceObservation,
    PlacementPreferenceSource,
)
from agentic_calendar.contracts.plan_diff import PlanDiff
from agentic_calendar.contracts.pooled_duration_model import (
    PooledBucket,
    PooledDurationModel,
    TimeOfDayBand,
)
from agentic_calendar.contracts.power_user import PerUserRefinement
from agentic_calendar.contracts.reason_codes import ReasonCode
from agentic_calendar.contracts.recommitment import RecommitmentChoice, RecommitmentRequest
from agentic_calendar.contracts.resume_intake_input import ResumeIntakeInput
from agentic_calendar.contracts.scheduler_output import SchedulerOutput, ScheduleStatus
from agentic_calendar.contracts.sponsor import SponsorStatus
from agentic_calendar.contracts.strategy_constraints import StrategyConstraints, UnfilledSlot
from agentic_calendar.contracts.syllabus_units import SyllabusUnits
from agentic_calendar.contracts.task_disposition import (
    DispositionSource,
    TaskDispositionRecord,
    TaskDispositionType,
)
from agentic_calendar.contracts.task_plan import TaskPlan
from agentic_calendar.contracts.telemetry import TelemetryEvent
from agentic_calendar.contracts.user_profile import UserProfile
from agentic_calendar.contracts.validation_result import (
    MAX_REPAIR_ATTEMPTS_LLM,
    NextAction,
    ValidationResult,
)
from agentic_calendar.drift.classifier import (
    DriftInput,
    FragmentationSignal,
    WeeklyCapacity,
)
from agentic_calendar.duration_estimation.pooled import (
    derive_time_of_day_band,
    resolve_effective_multipliers,
)
from agentic_calendar.llm_nodes.base import LLMNodeError
from agentic_calendar.llm_nodes.prose_attachment import (
    ProseAttachmentKind,
    ProseAttachmentRecord,
)
from agentic_calendar.llm_nodes.reflection_summary import ReflectionSummary
from agentic_calendar.llm_nodes.user_facing_explanation import (
    FitNoteRequest,
    FitNoteSlot,
    StorySummaryRequest,
    UserExplanation,
)
from agentic_calendar.narrative import SlotState, slot_coverage
from agentic_calendar.planning.diff import (
    PlanContentDiff,
    as_plan_diff,
    diff_plan_content,
)
from agentic_calendar.planning.drop import DropError, propose_dropped_plan
from agentic_calendar.planning.plan_version import (
    GenerationStep,
    GenerationStepRecord,
    LifecycleState,
    PlanVersion,
)
from agentic_calendar.planning.recovery import RecoveryRoute, propose_recovery_plan
from agentic_calendar.planning.replan import propose_recalibrated_plan
from agentic_calendar.planning.store import PlanVersionNotFoundError
from agentic_calendar.scheduler import schedule
from agentic_calendar.scheduler.adjustment import DraftAdjustment, validate_placements
from agentic_calendar.scheduler.inputs import FreeBusyInterval, SchedulerInput
from agentic_calendar.scheduler.policy import policy_from_user_profile
from agentic_calendar.skill_taxonomy import (
    SkillTaxonomyRegistry,
    load_registry,
    resolve,
    resolve_track,
)
from agentic_calendar.source_claims.curation import curate_claims
from agentic_calendar.supervisor.routing import route
from agentic_calendar.supervisor.state import SupervisorSignal as Sig
from agentic_calendar.supervisor.state import SupervisorState as S
from agentic_calendar.telemetry.calibration import calibrate
from agentic_calendar.telemetry.metrics import completion_rate
from agentic_calendar.templates import (
    PATHWAY_REGISTRY_VERSION,
    get_pathway,
    is_theme_in_vocabulary,
    list_pathways,
    pathways_for_track,
    theme_vocabulary,
)
from agentic_calendar.validation import validate_syllabus_units, validate_task_plan

from .environment import AppEnvironment
from .results import (
    AccountabilityResult,
    AdjustResult,
    AdjustViolation,
    AdjustWarning,
    ApproveResult,
    CanonicalSkill,
    DraftView,
    DropResult,
    EvidenceVocabularyResult,
    ExtractResumeResult,
    FitNotesResult,
    IngestResult,
    MeResult,
    OnboardResult,
    PathwayCard,
    PathwaySlotView,
    PathwaysResult,
    PlanDiffView,
    ProposeResult,
    RecommitResult,
    ReflectionHistoryEntry,
    RollbackCycleResult,
    StatusResult,
    StorySummaryResult,
    TelemetryItemOutcome,
    ThresholdFieldView,
    ThresholdSectionView,
    ThresholdsResult,
    TodayResult,
    TodayTask,
    WeeklyCheckinResult,
    WriteCycleResult,
)
from .state import OnboardingRecord, ReplanKind, RunRecord
from .tuning import TUNABLE_SECTIONS, scalar_fields

_log = get_logger(__name__)

MAX_SCHEDULER_PLANNER_ITERATIONS = 2
"""Axiom 05 bound: at most two Scheduler→Planner iterations per run."""

_REFLECTION_HISTORY_LIMIT = 10
"""Newest-first cap on the accountability view's reflection history — a
screenful for the SPA, not the user's full archive (which stays readable via
the prose store and its delete-for-user control)."""

DEFAULT_APPROVAL_TTL = timedelta(days=7)
"""Dogfood approvals must survive a human-paced approve→write gap, but still
expire: a week-old unexecuted approval requires an explicit re-approve."""

DEFAULT_TARGET_CALENDAR_ID = "agentic-calendar-dogfood"
"""Writes go to a dedicated secondary calendar only (axiom 06; Phase 9c)."""

HASH_CANONICALIZATION_VERSION = "v1"

#: Heuristic priors until calibrated (axiom: thresholds are priors). Both feed
#: the drift classifier's accountability/sponsor rules with caller-derived
#: observable behavior — the classifier itself never reads stores or profiles.
RECOMMITMENT_DECLINED_AFTER_DAYS = 7
"""An unanswered recommitment request older than this counts as an explicit
decline for the accountability-mismatch drift rule."""
SPONSOR_PRESSURE_WINDOW_DAYS = 14
"""Window for "recent" sponsor activity: a revocation inside it flags
``sponsor_reporting_disabled``; sent reports inside it count toward the
sponsor-pressure rule."""

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


def _clamp_evidence_multiplier(value: float) -> float:
    """Clamp a composed multiplier into the contract's calibration band.

    Pooled aggregation is a convex combination of in-band bucket values, so
    this only bites when an artifact's own clamp band is wider than the
    evidence contract's ``[0.5, 2.0]`` — clamping keeps composition total
    (never raises) and deterministic.
    """
    return min(EVIDENCE_MULTIPLIER_MAX, max(EVIDENCE_MULTIPLIER_MIN, value))


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
        # Pinned skill-taxonomy registry, loaded lazily once per service (the
        # checked-in JSON never changes at runtime; a vocabulary change is a
        # new file version behind a new deploy).
        self._skill_registry: SkillTaxonomyRegistry | None = None

    # ------------------------------------------------------------------ #
    # onboard
    # ------------------------------------------------------------------ #

    def onboard(self, payload: Mapping[str, Any]) -> OnboardResult:
        """Validate and persist the onboarding bundle.

        ``payload`` keys: ``user_profile`` (required), ``timezone`` (IANA,
        default UTC), ``motivation_profile`` (optional). Re-onboarding the
        same user replaces the bundle (profile edits are expected during
        dogfooding) but keeps the original ``created_at``.

        A ``pathway_selection`` on the profile is checked against the registry
        (NP-D): an unknown pathway, a stale registry-version pin, or an override
        naming a slot the pathway does not have is rejected with a typed
        ``reason_code`` and nothing is persisted. When the selection *changes*
        vs the stored profile, the syllabus, tasks, and schedule are invalidated
        per the profile-update policy (the accountability contract is not
        touched); evidence is never reset.
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

        rejection = self._reject_invalid_selection(record.user_profile)
        if rejection is not None:
            reason, detail = rejection
            return OnboardResult(
                user_id=record.user_id,
                created=prior is None,
                timezone=record.timezone,
                has_motivation_profile=record.motivation_profile is not None,
                status="rejected",
                reason_code=reason,
                detail=detail,
            )

        if prior is not None:
            # Re-onboarding (a profile edit) keeps the original created_at and the
            # user's inbound-calendar-sync preference (which onboarding never sets).
            record = OnboardingRecord.model_validate(
                record.model_dump()
                | {
                    "created_at": prior.created_at,
                    "inbound_calendar_sync_enabled": prior.inbound_calendar_sync_enabled,
                }
            )
            if self._selection_id(prior.user_profile) != self._selection_id(
                record.user_profile
            ):
                self._invalidate_for_pathway_change(record.user_id)
        env.state.save_onboarding(record)
        return OnboardResult(
            user_id=record.user_id,
            created=prior is None,
            timezone=record.timezone,
            has_motivation_profile=record.motivation_profile is not None,
        )

    @staticmethod
    def _selection_id(profile: UserProfile) -> str | None:
        """The profile's selected ``pathway_id``, or ``None`` when unselected.

        Slot-override edits keep the same ``pathway_id`` and never invalidate: a
        pathway *change* is what the policy table gates, and coverage recomputes
        against the new mapping on read (pathway-selection spec)."""
        selection = profile.pathway_selection
        return selection.pathway_id if selection is not None else None

    def _reject_invalid_selection(
        self, profile: UserProfile
    ) -> tuple[ReasonCode, str] | None:
        """Registry-membership check for the profile's selection (service layer).

        Returns a typed ``(reason_code, detail)`` for an unknown pathway, a stale
        registry-version pin, or an override naming a slot the pathway lacks;
        ``None`` when there is no selection or it is fully valid. Shape is already
        contract-checked (``PathwaySelection``); this is the semantic check the
        contract cannot make (it cannot see the registry)."""
        selection = profile.pathway_selection
        if selection is None:
            return None
        template = get_pathway(selection.pathway_id)
        if template is None:
            return (
                ReasonCode.UNKNOWN_PATHWAY_ID,
                f"pathway {selection.pathway_id!r} is not in the registry",
            )
        if selection.pathway_registry_version != PATHWAY_REGISTRY_VERSION:
            return (
                ReasonCode.PATHWAY_REGISTRY_VERSION_MISMATCH,
                f"selection pinned to registry version "
                f"{selection.pathway_registry_version!r}; the registry serves "
                f"{PATHWAY_REGISTRY_VERSION!r} — re-confirm on the current version",
            )
        slot_ids = {slot.slot_id for slot in template.evidence_slots}
        unknown = sorted(
            {o.slot_id for o in selection.slot_overrides if o.slot_id not in slot_ids}
        )
        if unknown:
            return (
                ReasonCode.UNKNOWN_EVIDENCE_SLOT,
                f"slot_overrides reference slots not in pathway "
                f"{selection.pathway_id!r}: {unknown}",
            )
        return None

    def _invalidate_for_pathway_change(self, user_id: str) -> None:
        """Invalidate syllabus + tasks + schedule after a pathway change (NP-D).

        Full discard: every non-terminal plan version is moved to ``DISCARDED``
        (so the tasks and schedule no longer reflect the superseded pathway and
        the read projections go empty), the stored syllabus is dropped (the next
        propose regenerates a fresh one against the new pathway), and a pending
        awaiting-approval run is retired through the existing reject edge so its
        stale draft can never be approved. The calendar is never touched here (no
        silent writes): already-written events supersede on the next
        approve→write, exactly like a replan. The accountability contract lives
        on the motivation profile and is deliberately left intact (profile-update
        policy)."""
        env = self._env
        now = env.clock.now()
        for plan_version in env.plan_store.list_for_user(user_id):
            if plan_version.state in (
                LifecycleState.DRAFT,
                LifecycleState.APPROVED,
                LifecycleState.ACTIVE,
            ):
                env.plan_store.save(
                    plan_version.transition_to(LifecycleState.DISCARDED, now=now)
                )
        env.state.delete_syllabus(user_id)
        latest = env.state.latest_run_for_user(user_id)
        if latest is not None and latest.state is S.AWAITING_USER_APPROVAL:
            self._transition(latest, Sig.USER_REJECTED)

    # ------------------------------------------------------------------ #
    # extract (résumé intake — persistence-free)
    # ------------------------------------------------------------------ #

    def _taxonomy_registry(self) -> SkillTaxonomyRegistry:
        if self._skill_registry is None:
            self._skill_registry = load_registry()
        return self._skill_registry

    def extract_resume(
        self, user_id: str, payload: Mapping[str, Any]
    ) -> ExtractResumeResult:
        """Run the ResumeIntakeNode over a pasted résumé — strictly persistence-free.

        ``payload`` keys: ``resume_text`` (required), ``draft_context``
        (optional draft wizard answers). The bundle is validated into
        :class:`ResumeIntakeInput` with ``user_id`` forced to the acting user
        (the onboard trust boundary) and ``allowed_weak_spots`` filled by this
        service from the pinned taxonomy's track slice — never from the client.
        An invalid payload raises pydantic's ``ValidationError`` (the router's
        standard 422 path) before any LLM call.

        This is a pre-run LLM call: the minted ``run_id`` carries the
        ``intake-`` prefix (llm-call-log spec) and no run or checkpoint state
        is touched. On success the proposal's skill surfaces are normalized
        through the taxonomy kernel: matched surfaces become
        ``skills_canonical``, unmatched ones are returned visibly flagged and
        never silently promoted. A node failure returns the typed
        ``reason_code`` in a normal result — unlike :meth:`_llm_failure` there
        is no run to route to ``UNRECOVERABLE_ERROR``; extraction failure is a
        local, retryable UX event. Profile persistence remains exclusively
        :meth:`onboard`.
        """
        env = self._env
        # First pass pins the contract (résumé bounds, draft-context shapes)
        # so track resolution below reads typed data, not raw client JSON.
        base = ResumeIntakeInput.model_validate(
            {**dict(payload), "user_id": user_id, "allowed_weak_spots": []}
        )
        registry = self._taxonomy_registry()
        track = resolve_track(base.draft_context.target_role)
        entries = (
            registry.entries_for_track(track) if track is not None else registry.entries
        )
        # Evidence-theme vocabulary is the pathway registry's per-track slice
        # (NP-C); empty when no track resolved or the track seeds no themes,
        # which the node treats as "propose no tags." Registry literals, not
        # client input — the node never imports the registry.
        allowed_themes = list(theme_vocabulary(track)) if track is not None else []
        intake = ResumeIntakeInput.model_validate(
            base.model_dump(mode="json")
            | {
                "allowed_weak_spots": [entry.display_name for entry in entries],
                "allowed_themes": allowed_themes,
            }
        )

        run_id = f"intake-{env.id_generator.new_id('run')}"
        try:
            proposal = env.nodes.resume_intake.run(run_id=run_id, intake=intake)
        except LLMNodeError as exc:
            reason = getattr(exc, "reason_code", None) or ReasonCode.LLM_CALL_FAILED
            return ExtractResumeResult(
                status="failed",
                run_id=run_id,
                user_id=user_id,
                reason_code=reason,
                detail=str(exc),
            )

        canonical: list[CanonicalSkill] = []
        unmatched: list[str] = []
        matched_ids: set[str] = set()
        for surface in proposal.skills:
            entry = resolve(surface, registry)
            if entry is None:
                unmatched.append(surface)
            elif entry.skill_id not in matched_ids:
                matched_ids.add(entry.skill_id)
                canonical.append(
                    CanonicalSkill(
                        skill_id=entry.skill_id,
                        display_name=entry.display_name,
                        surface=surface,
                    )
                )
        return ExtractResumeResult(
            status="ok",
            run_id=run_id,
            user_id=user_id,
            proposal=proposal,
            skills_canonical=canonical,
            skills_unmatched=unmatched,
            taxonomy_version=registry.taxonomy_version,
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
    # narrative pathways (NP-D) — deterministic selection resolution
    # ------------------------------------------------------------------ #

    def _resolve_selection_template(
        self, profile: UserProfile
    ) -> tuple[PathwayTemplate | None, bool]:
        """The registry template a profile's selection resolves to, plus a
        version-mismatch flag.

        Returns ``(None, False)`` when there is no selection or the ``pathway_id``
        is unknown, and ``(None, True)`` when the selection is pinned to a
        ``pathway_registry_version`` the registry no longer serves — surfaced for
        an explicit re-confirm, never silently re-mapped (pathway-selection spec).
        Only a live, matching selection yields ``(template, False)``.
        """
        selection = profile.pathway_selection
        if selection is None:
            return None, False
        template = get_pathway(selection.pathway_id)
        if template is None:
            return None, False
        if selection.pathway_registry_version != PATHWAY_REGISTRY_VERSION:
            return None, True
        return template, False

    def _pathway_constraints(
        self, profile: UserProfile
    ) -> tuple[StrategyConstraints | None, PathwayTemplate | None]:
        """Story-layer ``StrategyConstraints`` for the profile's selection.

        Returns ``(None, None)`` when nothing shapes generation (no selection, an
        unknown pathway, or a stale version pin). Otherwise the kernel computes
        the unfilled slots deterministically and they ride into the Strategist
        bundle as typed constraints (``pathway_id`` + ``unfilled_slots``); the
        resolved template is returned alongside so the validation gate disposes
        exactly what the prompt was told to respect.
        """
        template, _mismatch = self._resolve_selection_template(profile)
        if template is None:
            return None, None
        coverage = slot_coverage(profile, template)
        filled = {c.slot_id for c in coverage if c.state is SlotState.FILLED}
        unfilled = [
            UnfilledSlot(
                slot_id=slot.slot_id,
                title=slot.title,
                gap_module_hint=slot.gap_module_hint,
            )
            for slot in template.evidence_slots
            if slot.slot_id not in filled
        ]
        constraints = StrategyConstraints(
            pathway_id=template.pathway_id, unfilled_slots=unfilled
        )
        return constraints, template

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
        if (
            latest is not None
            and latest.state is S.REPLAN_REQUIRED
            # A pathway change (NP-D) discards the active plan out from under a
            # queued replan; with no plan to recalibrate, fall through to a fresh
            # cycle rather than dead-ending on "no plan is active".
            and self._env.plan_store.get_active(user_id) is not None
        ):
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

        # Deterministic pre-prompt curation (D1b, plan 03§5): expired, weak,
        # and over-cap claims never reach the Strategist, instead of steering
        # generation and then costing a repair round at validation. The
        # registry is built from the KEPT set so a citation of a curated-out
        # claim id is rejected as unknown, same as a hallucinated one.
        curation = curate_claims(
            list(env.claim_store.all()),
            now=env.clock.now(),
            config=env.tuning.claim_curation,
        )
        claims = list(curation.kept)
        if curation.dropped_total:
            correlated(_log, run_id=run.run_id).info(
                f"claim curation dropped {curation.dropped_total} claim(s) "
                f"before prompting: {len(curation.dropped_expired)} expired, "
                f"{len(curation.dropped_below_floor)} below confidence floor, "
                f"{len(curation.dropped_over_host_cap)} over per-host cap "
                "(heuristic priors; tuning section claim_curation)"
            )
        registry = {c.claim_id: c for c in claims}

        # Narrative shaping (NP-D): when the profile carries a confirmed pathway
        # selection that resolves against the pinned registry, the kernel
        # computes the unfilled slots deterministically and the Strategist is
        # *told* the gaps as typed constraints — never asked to find them. The
        # same selected template + bound gate the output. No selection ⇒
        # ``constraints`` is None and this is byte-identical to today.
        constraints, selected_pathway = self._pathway_constraints(profile)
        max_slot_modules = (
            constraints.max_slot_modules if constraints is not None else 3
        )

        syllabus: SyllabusUnits | None = None
        for attempt in range(MAX_REPAIR_ATTEMPTS_LLM + 1):
            try:
                candidate = env.nodes.strategist.run(
                    run_id=run.run_id,
                    user_profile=profile,
                    source_claims=claims,
                    strategy_constraints=constraints,
                )
            except LLMNodeError as exc:
                return self._propose_failure(self._llm_failure(run, exc))
            run = self._transition(run, Sig.STRATEGIST_OUTPUT_PRODUCED)
            result = validate_syllabus_units(
                candidate,
                claim_registry=registry,
                now=env.clock.now(),
                run_id=run.run_id,
                selected_pathway=selected_pathway,
                max_slot_modules=max_slot_modules,
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
        excluded = sorted(self._completed_or_dropped_ids(onboarding.user_id))

        def planner_pass(run_id: str, repair: ValidationResult | None) -> TaskPlan:
            return env.nodes.planner.run(
                run_id=run_id,
                syllabus=bound_syllabus,
                user_profile=onboarding.user_profile,
                repair=repair,
                excluded_tasks=excluded,
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
        excluded = sorted(self._completed_or_dropped_ids(onboarding.user_id))
        # D2: the replan Planner sees the user's recent reflections as an
        # advisory behavioral-hints block beside the exclusions — the drift
        # prose that caused this replan informs sizing/emphasis. Frozen at
        # decision time, like the exclusion list.
        hints = self._recent_reflections(onboarding.user_id)
        # D4 stage 1: anchor the replan on what the user already approved —
        # the active plan's surviving tasks (not completed/dropped) plus the
        # recovery mode go into the Planner context with a
        # preserve-unless-affected instruction. Context-only anchoring:
        # validation is unchanged, and validator-enforced preservation stays
        # axiom-20 Phase 2/3 work.
        excluded_set = set(excluded)
        surviving = tuple(
            t for t in active.plan.tasks if t.task_id not in excluded_set
        )
        return lambda run_id, repair: env.nodes.planner.run(
            run_id=run_id,
            syllabus=syllabus,
            user_profile=onboarding.user_profile,
            repair=repair,
            excluded_tasks=excluded,
            behavioral_hints=hints,
            prior_plan_tasks=surviving,
            replan_mode=mode,
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

    def _placement_evidence(
        self,
        onboarding: OnboardingRecord,
        *,
        pooled_model: PooledDurationModel | None = None,
        refinement: PerUserRefinement | None = None,
    ) -> PlacementEvidence:
        """Compose the scheduler's placement evidence (axiom 05 evidence term).

        The pooled/refined tiers are dormant in production: no
        pooled-artifact store exists in the solo MVP and the power-user
        refinement tier has no runtime producer, so the pipeline calls this
        with both params ``None`` — these parameters are the seam a future
        artifact store plugs into, exercised end-to-end by tests only.
        Nothing user-facing may describe pooled-evidence placement as live
        until an artifact actually flows here. The REVEALED tier is the live
        tier: it aggregates this user's own drag-adjust / reconcile-adopt
        observations from the placement-preference store (axiom 05
        "Revealed-preference term") — with none recorded yet, composed
        evidence stays empty and the scheduler runs evidence-free.

        Pooled cells are consent-gated (ADR-0007) exactly like pooled
        duration serving; the gate is consulted — and its audit entry
        written — only when a pooled artifact is actually offered, so the
        dormant path adds zero audit rows. The refinement tier is the user's
        own data and is not consent-gated (mirroring
        ``resolve_duration_multiplier``). Cells condition on the user's
        ``experience_level`` and marginalize the remaining non-(category,
        band) bucket features; a cell whose combined ``weighted_sample``
        falls below ``pooled_serving.serving_floor`` is not emitted
        (serving-floor discipline, for both tiers). Revealed cells are
        governed by their own count threshold instead
        (``revealed_min_observations`` within ``revealed_window_days``, both
        journaled in ``[scheduler_placement]``); the clock is read here in
        the app layer, never in the scheduler.
        """
        env = self._env
        floor = env.tuning.pooled_serving.serving_floor
        cells: list[EvidenceCell] = []
        if pooled_model is not None:
            gate_decision = env.consent_gate.check(
                onboarding.user_id,
                DataAccessPurpose.POOLED_SERVING,
                DataAccessor.SERVING_PIPELINE,
            )
            if gate_decision.allowed:
                grouped: dict[
                    tuple[TaskCategory, TimeOfDayBand], list[PooledBucket]
                ] = {}
                for bucket in pooled_model.buckets:
                    if (
                        bucket.experience_level
                        is not onboarding.user_profile.experience_level
                    ):
                        continue
                    grouped.setdefault(
                        (bucket.category, bucket.time_of_day_band), []
                    ).append(bucket)
                for (category, band), buckets in grouped.items():
                    combined = sum(b.weighted_sample for b in buckets)
                    if combined < floor:
                        continue
                    if len(buckets) == 1:
                        # No aggregation needed; avoids float drift vs the
                        # bucket value (pooled-serving precedent).
                        multiplier = buckets[0].multiplier
                    else:
                        multiplier = (
                            sum(b.multiplier * b.weighted_sample for b in buckets)
                            / combined
                        )
                    cells.append(
                        EvidenceCell(
                            category=category,
                            time_of_day_band=band,
                            multiplier=_clamp_evidence_multiplier(multiplier),
                            weighted_sample=combined,
                            source=EvidenceSource.POOLED,
                        )
                    )
        if refinement is not None:
            for entry in refinement.entries:
                if entry.weighted_sample < floor:
                    continue
                cells.append(
                    EvidenceCell(
                        category=entry.category,
                        time_of_day_band=entry.time_of_day_band,
                        multiplier=_clamp_evidence_multiplier(entry.multiplier),
                        weighted_sample=entry.weighted_sample,
                        source=EvidenceSource.PER_USER_REFINED,
                    )
                )
        observations = env.placement_preference_store.list_for_user(
            onboarding.user_id
        )
        if observations:
            placement_cfg = env.tuning.scheduler_placement
            cutoff = env.clock.now() - timedelta(
                days=placement_cfg.revealed_window_days
            )
            counts: dict[tuple[TaskCategory, TimeOfDayBand], int] = {}
            for observation in observations:
                if observation.observed_at < cutoff:
                    continue
                key = (observation.category, observation.time_of_day_band)
                counts[key] = counts.get(key, 0) + 1
            for (category, band), count in counts.items():
                if count < placement_cfg.revealed_min_observations:
                    continue
                cells.append(
                    EvidenceCell(
                        category=category,
                        time_of_day_band=band,
                        multiplier=None,
                        weighted_sample=float(count),
                        source=EvidenceSource.REVEALED,
                    )
                )
        cells.sort(
            key=lambda c: (c.category.value, c.time_of_day_band.value, c.source.value)
        )
        return PlacementEvidence(cells=cells)

    def _record_placement_observation(
        self,
        *,
        user_id: str,
        task_id: str,
        category: TaskCategory,
        local_start: datetime,
        source: PlacementPreferenceSource,
    ) -> None:
        """Journal one revealed-preference observation (placement-preference spec).

        ``local_start`` must already carry the user's wall clock — the band
        is the hour the user moved the task *into*. Task ids and enums only;
        never raw event titles (axiom 06).
        """
        env = self._env
        env.placement_preference_store.append(
            PlacementPreferenceObservation(
                observation_id=env.id_generator.new_id("prefobs"),
                user_id=user_id,
                task_id=task_id,
                category=category,
                time_of_day_band=derive_time_of_day_band(local_start.hour),
                observed_at=env.clock.now(),
                source=source,
            )
        )

    def _completed_or_dropped_ids(self, user_id: str) -> set[str]:
        """Task ids the user has completed or dropped, across all plan versions.

        The union of the COMPLETED and DROPPED disposition projections. Feeds the
        scheduler's completion-aware filter (the previously-dead
        ``SchedulerInput.completed_task_ids`` stub) and the completion-relative
        drag-to-adjust advisory check (ADR-0008; task-disposition spec).
        """
        store = self._env.disposition_store
        return store.task_ids_with_disposition(
            user_id, TaskDispositionType.COMPLETED
        ) | store.task_ids_with_disposition(user_id, TaskDispositionType.DROPPED)

    def _mirror_completed_dispositions(
        self, user_id: str, plan_version: str, completed_task_ids: set[str]
    ) -> None:
        """Record a COMPLETED disposition (``source=SYSTEM``) per completed task.

        Idempotent: the ``disposition_id`` is content-derived from
        ``(user_id, plan_version, task_id)``, so re-ingesting the same completion
        is a no-op. Completion data already lived in telemetry; this mirrors it
        into the durable completion/drop memory the scheduler projection and the
        advisory check read (task-disposition spec).
        """
        store = self._env.disposition_store
        now = self._env.clock.now()
        for task_id in sorted(completed_task_ids):
            disposition_id = f"disp_{user_id}_{plan_version}_{task_id}_completed"
            if store.exists(disposition_id):
                continue
            store.append(
                TaskDispositionRecord(
                    disposition_id=disposition_id,
                    user_id=user_id,
                    plan_version=plan_version,
                    task_id=task_id,
                    disposition=TaskDispositionType.COMPLETED,
                    reason_code=None,
                    source=DispositionSource.SYSTEM,
                    created_at=now,
                )
            )

    def _record_event_deleted(
        self, user_id: str, plan_version: str, task_id: str, *, now: datetime
    ) -> None:
        """Durable memory that the task's calendar event was deleted externally.

        Idempotent: the ``disposition_id`` is content-derived, so repeated
        reconcile pulls of the same deletion are a no-op. Event memory only —
        the task stays planned, and EVENT_DELETED never joins the
        completed/dropped scheduler projection (axiom 06 lines 249-253:
        cancellation-on-delete is opt-in; task-disposition spec).
        """
        store = self._env.disposition_store
        disposition_id = f"disp_{user_id}_{plan_version}_{task_id}_event_deleted"
        if store.exists(disposition_id):
            return
        store.append(
            TaskDispositionRecord(
                disposition_id=disposition_id,
                user_id=user_id,
                plan_version=plan_version,
                task_id=task_id,
                disposition=TaskDispositionType.EVENT_DELETED,
                reason_code=ReasonCode.EXTERNAL_EVENT_DELETED,
                source=DispositionSource.SYSTEM,
                created_at=now,
            )
        )

    def _event_deleted_ids(self, user_id: str, plan_version: str) -> set[str]:
        """Task ids of ``plan_version`` whose calendar event the user deleted
        externally (EVENT_DELETED dispositions).

        Scoped to a single plan version — a later regeneration mints fresh
        events, so its tasks start clean. Feeds only the read projections
        (``DraftView.deleted_task_ids``, ``TodayTask.deleted``); deliberately
        NOT unioned into ``_completed_or_dropped_ids``.
        """
        return {
            record.task_id
            for record in self._env.disposition_store.list_for_plan(
                user_id, plan_version
            )
            if record.disposition is TaskDispositionType.EVENT_DELETED
        }

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
        completed_or_dropped = sorted(self._completed_or_dropped_ids(onboarding.user_id))
        dropped_ids = env.disposition_store.task_ids_with_disposition(
            onboarding.user_id, TaskDispositionType.DROPPED
        )

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
                    resurrected = sorted(
                        dropped_ids & {t.task_id for t in candidate.tasks}
                    )
                    if resurrected:
                        correlated(_log, run_id=run.run_id).warning(
                            f"regeneration reproduced dropped task(s) {resurrected}; "
                            "advisory exclusion only (axiom 20 partial regen is "
                            "Phase 2/3)"
                        )
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
                    validation=result,
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
                    completed_task_ids=completed_or_dropped,
                    # Pooled/refined tiers are dormant in prod (no artifact
                    # to pass); the REVEALED tier serves live from the
                    # user's own observations (see _placement_evidence).
                    placement_evidence=self._placement_evidence(onboarding),
                    horizon_start=horizon_start,
                    horizon_end=horizon_start + timedelta(days=horizon_days),
                ),
                scoring=env.tuning.scheduler_placement,
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

        # D4 stage 2: a continuation from an existing plan carries the
        # deterministic old→new content diff, so review/approval can show the
        # delta instead of a wall of blocks. Computed by code from the two
        # persisted plans (axiom 15); recomputable any time, so not stored.
        plan_diff: PlanDiff | None = None
        if parent_plan_version is not None:
            parent = env.plan_store.get(onboarding.user_id, parent_plan_version)
            if parent is not None:
                plan_diff = as_plan_diff(
                    diff_plan_content(parent.plan, plan),
                    diff_id=env.id_generator.new_id("diff"),
                    now=now,
                    field_change_reason=(
                        # The replan's typed driver, applied uniformly — code
                        # cannot attribute per-field causes in a regenerated
                        # plan (see planning/diff.py).
                        ReasonCode.USER_DURATION_CALIBRATION
                        if run.replan_kind is ReplanKind.RECALIBRATION
                        else ReasonCode.DRIFT_REMEDIATION
                    ),
                )

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
            plan_diff=plan_diff,
        )

    def _llm_failure(self, run: RunRecord, exc: LLMNodeError) -> RunRecord:
        """Typed panic: an LLM node failed beyond its bounded internal retries."""
        reason = getattr(exc, "reason_code", None) or ReasonCode.LLM_CALL_FAILED
        return self._transition(run, Sig.UNRECOVERABLE_ERROR, reason_code=reason)

    def _persist_prose(
        self,
        run: RunRecord,
        kind: ProseAttachmentKind,
        *,
        summary: str,
        detail: Sequence[str],
    ) -> None:
        """Make user-facing prose durable (spec: prose-attachment).

        Display + advisory-context data only — the run record's typed fields
        stay the control plane; this copy exists so a user returning to a
        parked run can read what the product already told them."""
        env = self._env
        env.prose_store.append(
            ProseAttachmentRecord(
                prose_attachment_id=env.id_generator.new_id("prose"),
                user_id=run.user_id,
                run_id=run.run_id,
                plan_version=run.plan_version,
                kind=kind,
                summary=summary,
                detail=tuple(detail),
                reason_code=run.reason_code,
                created_at=env.clock.now(),
            )
        )

    def _recent_reflections(self, user_id: str, *, limit: int = 3) -> list[str]:
        """The user's last few persisted reflection sentences, oldest first.

        Advisory-context reader (D2): feeds the reflection node's continuity
        block and the replan Planner's behavioral-hints block. Prose only —
        the strings are rendered for a prompt and never parsed back; nothing
        deterministic reads them. Summary lines only (not detail) to keep the
        injected block small; the date prefix lets the model see spacing
        between notes without any clock access."""
        records = [
            r
            for r in self._env.prose_store.list_for_user(user_id)
            if r.kind is ProseAttachmentKind.REFLECTION
        ]
        return [
            f"{r.created_at.date().isoformat()}: {r.summary}" for r in records[-limit:]
        ]

    def _propose_failure(
        self,
        run: RunRecord,
        *,
        validation: ValidationResult | None = None,
        explanation: UserExplanation | None = None,
        output: SchedulerOutput | None = None,
    ) -> ProposeResult:
        if explanation is not None:
            # By this point the terminal transition already stamped the run's
            # typed reason_code — the persisted copy carries it for display.
            self._persist_prose(
                run,
                ProseAttachmentKind.EXPLANATION,
                summary=explanation.summary,
                detail=explanation.detail,
            )
        return ProposeResult(
            run_id=run.run_id,
            user_id=run.user_id,
            state=run.state,
            reason_code=run.reason_code,
            replan_kind=run.replan_kind,
            recovery_mode=run.recovery_mode,
            unscheduled_tasks=list(output.unscheduled_tasks) if output else [],
            repair_options=list(output.repair_options) if output else [],
            violations=list(validation.violations) if validation else [],
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

        review = validate_placements(
            candidate.entries,
            plan=plan_version.plan,
            policy=policy_from_user_profile(onboarding.user_profile),
            free_busy=[FreeBusyInterval.model_validate(dict(fb)) for fb in free_busy],
            tz=tz,
            completed_or_dropped_task_ids=self._completed_or_dropped_ids(user_id),
        )
        if review.conflicts:
            return AdjustResult(
                run_id=run.run_id,
                user_id=user_id,
                state=run.state,
                applied=False,
                reason_code=review.conflicts[0].reason_code,
                violations=[
                    AdjustViolation(
                        task_id=conflict.task_id,
                        reason_code=conflict.reason_code,
                        detail=conflict.detail,
                    )
                    for conflict in review.conflicts
                ],
            )

        env.state.save_draft(user_id, candidate)
        # Pure artifact swap: the run stays in AWAITING_USER_APPROVAL (no
        # lifecycle transition) — only the pending draft it points at changes.
        # An advisory (DEPENDENCY_ADVISORY) does not block: the move is applied
        # and the heads-up rides in ``warnings`` (ADR-0008).
        run = self._save_run(run, draft_schedule_id=candidate.draft_schedule_id)
        # Each applied drag is a revealed statement of preferred time-of-day
        # for the task's category (axiom 05 "Revealed-preference term");
        # rejected moves recorded nothing — they returned above.
        category_by_task = {t.task_id: t.category for t in plan_version.plan.tasks}
        for task_id in sorted(new_starts):
            category = category_by_task.get(task_id)
            if category is None:  # draft entry outside the plan; defensive
                continue
            self._record_placement_observation(
                user_id=user_id,
                task_id=task_id,
                category=category,
                local_start=new_starts[task_id],
                source=PlacementPreferenceSource.DRAG_ADJUST,
            )
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
            warnings=[
                AdjustWarning(
                    task_id=warning.task_id,
                    reason_code=warning.reason_code,
                    detail=warning.detail,
                )
                for warning in review.warnings
            ],
        )

    # ------------------------------------------------------------------ #
    # reconcile (inbound calendar edits; calendar-reconciliation spec)
    # ------------------------------------------------------------------ #

    def reconcile(
        self,
        user_id: str,
        *,
        target_calendar_id: str,
        free_busy: Sequence[Mapping[str, Any]] = (),
        enabled: bool,
    ) -> CalendarReconciliationResult:
        """Inbound, adopt-if-valid reconciliation of the user's own edits to
        app-created events on their dedicated calendar.

        Canonical spec: ``docs/specs/calendar-reconciliation.schema.md``. Read-only
        against the calendar — it never writes (axiom 06: the Calendar Write
        Manager is the only writer). Off unless ``enabled`` (axiom 06 lines
        249-253: the in-app schedule is the system of record, so treating an
        external edit as authoritative is opt-in). A valid move/resize is adopted
        into a fresh draft of the same plan version with no calendar write and no
        re-approval — overlap, daily load, and prerequisite ordering are
        advisory for an external move (ADR-0009 / ADR-0010 / ADR-0008), so only
        the hard policy bound (allowed hours/weekend) rejects. A rejected move, or a
        deletion, is flagged (``user_modified_bool``) and left for the drift
        loop — never silently rewritten, and a deletion is never silently
        cancelled.
        """
        env = self._env
        onboarding = self._require_onboarding(user_id)
        active = env.plan_store.get_active(user_id)
        run = env.state.latest_run_for_user(user_id)
        if active is None or run is None or run.draft_schedule_id is None:
            raise CycleError("no active plan to reconcile")
        draft = env.state.get_draft(run.draft_schedule_id)
        if draft is None or draft.plan_version != active.plan_version:
            raise CycleError("active plan has no current draft to reconcile")

        now = env.clock.now()
        run_id = run.run_id
        plan_version = active.plan_version

        def result(
            outcome: ReconciliationOutcome,
            *,
            deltas: tuple[CalendarEventDelta, ...] = (),
            adopted_draft_schedule_id: str | None = None,
        ) -> CalendarReconciliationResult:
            return CalendarReconciliationResult(
                run_id=run_id,
                plan_version=plan_version,
                reconciled_at=now,
                target_calendar_id=target_calendar_id,
                outcome=outcome,
                adopted_draft_schedule_id=adopted_draft_schedule_id,
                deltas=deltas,
            )

        if not enabled:
            return result(ReconciliationOutcome.SYNC_DISABLED)
        # Never interleave with our own in-flight write (axiom 13).
        if run.state in (S.CALENDAR_WRITE_APPROVED, S.CALENDAR_WRITE_IN_PROGRESS):
            return result(ReconciliationOutcome.DEFERRED)

        # The latest live mapping per task of the active plan — each carries the
        # event id and the time WE believe the event sits at.
        mappings: dict[str, CalendarEventMapping] = {}
        for task in active.plan.tasks:
            history = env.mapping_store.list_for_task(task.task_id)
            if not history:
                continue
            latest = history[-1]
            if latest.calendar_event_id is not None and latest.calendar_write_status in (
                CalendarWriteStatus.WRITTEN,
                CalendarWriteStatus.VERIFIED,
            ):
                mappings[task.task_id] = latest
        if not mappings:
            return result(ReconciliationOutcome.NO_CHANGE)

        # Pull each event back (scoped to our own ids) and classify the delta.
        user_tz = onboarding.tzinfo()
        change_by_task: dict[
            str, tuple[CalendarEditType, datetime | None, datetime | None]
        ] = {}
        try:
            for task_id, mapping in mappings.items():
                event_id = mapping.calendar_event_id
                if event_id is None:  # filtered above; defensive
                    continue
                record = env.write_manager.read_event(
                    target_calendar_id=target_calendar_id, calendar_event_id=event_id
                )
                if record is None:
                    change_by_task[task_id] = (CalendarEditType.DELETED, None, None)
                    continue
                # Google returns event instants normalized to UTC (the write
                # path stores timeZone=UTC), but draft entries and mappings
                # carry the USER's wall clock — the SPA renders the offset
                # embedded in the ISO string. Restamp before classifying so an
                # adopted time isn't stored (and drawn) as UTC digits hours off;
                # the comparisons below are instant-based either way.
                obs_start = record.scheduled_start.astimezone(user_tz)
                obs_end = record.scheduled_end.astimezone(user_tz)
                if (
                    obs_start == mapping.scheduled_start
                    and obs_end == mapping.scheduled_end
                ):
                    change_by_task[task_id] = (
                        CalendarEditType.UNCHANGED,
                        obs_start,
                        obs_end,
                    )
                else:
                    same_dur = (obs_end - obs_start) == (
                        mapping.scheduled_end - mapping.scheduled_start
                    )
                    change_by_task[task_id] = (
                        CalendarEditType.MOVED if same_dur else CalendarEditType.RESIZED,
                        obs_start,
                        obs_end,
                    )
        except CalendarWriterError:
            # A failed read-back is transient; reconcile again later, write nothing.
            return result(ReconciliationOutcome.DEFERRED)

        edited = {
            CalendarEditType.MOVED,
            CalendarEditType.RESIZED,
            CalendarEditType.DELETED,
        }
        moved = {
            t
            for t, (k, _, _) in change_by_task.items()
            if k in (CalendarEditType.MOVED, CalendarEditType.RESIZED)
        }
        if not any(k in edited for k, *_ in change_by_task.values()):
            return result(ReconciliationOutcome.NO_CHANGE)

        # Candidate placement we WOULD adopt: moved/resized at the observed time,
        # everything else (incl. a deleted event, which stays in our plan) at its
        # recorded time. Validate the WHOLE set and adopt all-or-nothing, exactly
        # like a UI drag (draft-schedule spec, "Server-side re-validation").
        candidate_entries: list[DraftScheduleEntry] = []
        for entry in draft.entries:
            change = change_by_task.get(entry.task_id)
            adopted_times: tuple[datetime, datetime] | None = None
            if change is not None and change[0] in (
                CalendarEditType.MOVED,
                CalendarEditType.RESIZED,
            ):
                _, cand_start, cand_end = change
                if cand_start is not None and cand_end is not None:
                    adopted_times = (cand_start, cand_end)
            if adopted_times is not None:
                candidate_entries.append(
                    DraftScheduleEntry(
                        task_id=entry.task_id,
                        start=adopted_times[0],
                        end=adopted_times[1],
                        calendar_event_status=entry.calendar_event_status,
                    )
                )
            else:
                candidate_entries.append(entry)

        review = validate_placements(
            candidate_entries,
            plan=active.plan,
            policy=policy_from_user_profile(onboarding.user_profile),
            free_busy=[FreeBusyInterval.model_validate(dict(fb)) for fb in free_busy],
            tz=user_tz,
            completed_or_dropped_task_ids=self._completed_or_dropped_ids(user_id),
            # An external move already happened on the user's own calendar:
            # overlap warns (OVERLAP_ADVISORY, ADR-0009) and daily load warns
            # (DAILY_LOAD_ADVISORY, ADR-0010) instead of rejecting.
            overlap_advisory=True,
            daily_load_advisory=True,
        )
        # Advisory ordering (DEPENDENCY_ADVISORY, ADR-0008), advisory overlap
        # (OVERLAP_ADVISORY, ADR-0009), and advisory daily load
        # (DAILY_LOAD_ADVISORY, ADR-0010) do NOT block adoption; only the hard
        # policy bound (allowed hours/weekend) rejects an external move.
        adopt = bool(moved) and not review.conflicts
        conflict_code = {c.task_id: c.reason_code for c in review.conflicts}
        fallback_code = review.conflicts[0].reason_code if review.conflicts else None
        # One advisory heads-up per adopted delta, by precedence:
        # DAILY_LOAD_ADVISORY > DEPENDENCY_ADVISORY > OVERLAP_ADVISORY — the
        # daily cap is a bound the user explicitly configured and its breach is
        # invisible on the grid; the overlap is visible on the grid itself
        # (spec, "Adopt-If-Valid Rules").
        advisory_rank = {
            ReasonCode.DAILY_LOAD_ADVISORY: 0,
            ReasonCode.DEPENDENCY_ADVISORY: 1,
            ReasonCode.OVERLAP_ADVISORY: 2,
        }
        advisory_code: dict[str, ReasonCode] = {}
        for w in review.warnings:
            held = advisory_code.get(w.task_id)
            if held is None or advisory_rank[w.reason_code] < advisory_rank[held]:
                advisory_code[w.task_id] = w.reason_code

        deltas: list[CalendarEventDelta] = []
        category_by_task = {t.task_id: t.category for t in active.plan.tasks}
        for task_id, (kind, seen_start, seen_end) in sorted(change_by_task.items()):
            mapping = mappings[task_id]
            disposition = ReconciliationDisposition.UNCHANGED
            code: ReasonCode | None = None
            if kind is CalendarEditType.DELETED:
                env.mapping_store.record_external_edit(mapping.run_id, task_id, now=now)
                disposition = ReconciliationDisposition.FLAGGED_DELETED
                code = ReasonCode.EXTERNAL_EVENT_DELETED
                # Durable, idempotent deletion memory (never a completion) — the
                # read projections surface it as "deleted from calendar".
                self._record_event_deleted(user_id, plan_version, task_id, now=now)
            elif kind in (CalendarEditType.MOVED, CalendarEditType.RESIZED):
                if adopt:
                    env.mapping_store.record_external_edit(
                        mapping.run_id,
                        task_id,
                        now=now,
                        new_start=seen_start,
                        new_end=seen_end,
                    )
                    disposition = ReconciliationDisposition.ADOPTED
                    # An adopted move carries at most one advisory heads-up:
                    # DAILY_LOAD_ADVISORY (ADR-0010), DEPENDENCY_ADVISORY
                    # (ADR-0008), or OVERLAP_ADVISORY (ADR-0009); otherwise null.
                    code = advisory_code.get(task_id)
                    # An adopted external move is a revealed statement of
                    # preferred time-of-day (axiom 05); rejected moves and
                    # deletions never record one. ``seen_start`` was already
                    # restamped into the user's wall clock at classification.
                    if seen_start is not None:
                        self._record_placement_observation(
                            user_id=user_id,
                            task_id=task_id,
                            category=category_by_task[task_id],
                            local_start=seen_start,
                            source=PlacementPreferenceSource.RECONCILE_ADOPT,
                        )
                else:
                    env.mapping_store.record_external_edit(mapping.run_id, task_id, now=now)
                    disposition = ReconciliationDisposition.REJECTED
                    code = conflict_code.get(task_id, fallback_code)
            deltas.append(
                CalendarEventDelta(
                    task_id=task_id,
                    calendar_event_id=mapping.calendar_event_id,
                    change_type=kind,
                    recorded_start=mapping.scheduled_start,
                    recorded_end=mapping.scheduled_end,
                    observed_start=seen_start,
                    observed_end=seen_end,
                    disposition=disposition,
                    reason_code=code,
                )
            )

        adopted_draft_schedule_id: str | None = None
        if adopt:
            adopted_draft = DraftSchedule(
                draft_schedule_id=env.id_generator.new_id("draft"),
                plan_version=plan_version,
                entries=tuple(candidate_entries),
                created_at=now,
            )
            env.state.save_draft(user_id, adopted_draft)
            self._save_run(run, draft_schedule_id=adopted_draft.draft_schedule_id)
            adopted_draft_schedule_id = adopted_draft.draft_schedule_id

        adopted_count = sum(
            1 for d in deltas if d.disposition is ReconciliationDisposition.ADOPTED
        )
        flagged_count = sum(
            1
            for d in deltas
            if d.disposition
            in (
                ReconciliationDisposition.REJECTED,
                ReconciliationDisposition.FLAGGED_DELETED,
            )
        )
        if adopted_count and flagged_count:
            outcome = ReconciliationOutcome.MIXED
        elif adopted_count:
            outcome = ReconciliationOutcome.ADOPTED
        elif flagged_count:
            outcome = ReconciliationOutcome.FLAGGED
        else:
            outcome = ReconciliationOutcome.NO_CHANGE
        return result(
            outcome,
            deltas=tuple(deltas),
            adopted_draft_schedule_id=adopted_draft_schedule_id,
        )

    # ------------------------------------------------------------------ #
    # drop (completion/drop memory)
    # ------------------------------------------------------------------ #

    def drop_tasks(
        self,
        user_id: str,
        task_ids: Sequence[str],
        *,
        run_id: str | None = None,
    ) -> DropResult:
        """Drop unfinished tasks from the active plan (deterministic, draft-only).

        Removes ``task_ids`` from the active plan, prunes them from survivors'
        dependencies, and keeps survivors at their EXISTING placements
        (``planning/drop.py``). Produces a survivors-only DRAFT on a fresh run
        routed straight to approval — the active plan stays ACTIVE until the drop
        is approved + written (a delete-only write that removes only the dropped
        events). On reject the fresh run discards; the active plan is untouched.
        """
        env = self._env
        if not task_ids:
            raise CycleError("no tasks to drop")
        self._require_onboarding(user_id)
        active_run = self._require_run(user_id, run_id, expected=S.ACTIVE_PLAN)
        active = env.plan_store.get_active(user_id)
        if active is None:
            raise CycleError("no active plan to drop from")
        if active_run.draft_schedule_id is None:
            raise CycleError("active run has no draft schedule to carry survivors forward")
        current_draft = env.state.get_draft(active_run.draft_schedule_id)
        if current_draft is None:
            raise CycleError(f"draft {active_run.draft_schedule_id!r} not found")

        try:
            proposal = propose_dropped_plan(
                active,
                current_draft,
                task_ids,
                id_generator=env.id_generator,
                clock=env.clock,
            )
        except DropError as exc:
            raise CycleError(str(exc)) from exc

        now = env.clock.now()
        env.plan_store.save(proposal.plan_version)
        env.state.save_draft(user_id, proposal.draft_schedule)
        # Record the drop in durable memory BEFORE the write so a re-propose /
        # regen sees it (idempotent content-derived id; task-disposition spec).
        for task_id in proposal.dropped_ids:
            disposition_id = f"disp_{user_id}_{active.plan_version}_{task_id}_dropped"
            if not env.disposition_store.exists(disposition_id):
                env.disposition_store.append(
                    TaskDispositionRecord(
                        disposition_id=disposition_id,
                        user_id=user_id,
                        plan_version=active.plan_version,
                        task_id=task_id,
                        disposition=TaskDispositionType.DROPPED,
                        reason_code=ReasonCode.TASK_DROPPED_BY_USER,
                        source=DispositionSource.USER,
                        created_at=now,
                    )
                )
        # A fresh run carries the drop to approval (reject leaves the active plan
        # intact); write removes only these tasks' events (delete-only).
        run = RunRecord(
            run_id=env.id_generator.new_id("run"),
            user_id=user_id,
            state=S.INITIAL,
            created_at=now,
            updated_at=now,
        )
        env.state.save_run(run)
        run = self._transition(
            run,
            Sig.DROP_REQUESTED,
            plan_version=proposal.plan_version.plan_version,
            draft_schedule_id=proposal.draft_schedule.draft_schedule_id,
            drop_task_ids=proposal.dropped_ids,
        )
        return DropResult(
            run_id=run.run_id,
            user_id=user_id,
            state=run.state,
            plan_version=proposal.plan_version.plan_version,
            parent_plan_version=active.plan_version,
            draft_schedule_id=proposal.draft_schedule.draft_schedule_id,
            draft_payload_hash=canonical_payload_hash(
                proposal.draft_schedule, HASH_CANONICALIZATION_VERSION
            ),
            dropped_task_ids=list(proposal.dropped_ids),
            survivor_task_count=len(proposal.draft_schedule.entries),
        )

    # ------------------------------------------------------------------ #
    # write
    # ------------------------------------------------------------------ #

    def _task_titles_for(
        self, user_id: str, plan_version: str | None
    ) -> dict[str, str]:
        """``task_id`` → title map for calendar-event summaries (display-only).

        Returns ``{}`` when the plan version is unknown or not found — an
        approved write must never fail over a display field, so the events
        fall back to the adapter's generic summary. The fallback is logged so
        it stays observable.
        """
        if plan_version is None:
            correlated(_log, user_id=user_id).warning(
                "task titles unavailable (no plan_version); calendar events "
                "will use the generic fallback summary"
            )
            return {}
        try:
            plan = self._env.plan_store.get(user_id, plan_version)
        except PlanVersionNotFoundError:
            correlated(_log, user_id=user_id, plan_version=plan_version).warning(
                "task titles unavailable (plan version not found); calendar "
                "events will use the generic fallback summary"
            )
            return {}
        return {task.task_id: task.title for task in plan.plan.tasks}

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

        # The planned side-effect count every outcome (success OR failure)
        # reports, so the "N / M verified" surface never renders a planned
        # total of 0 on a failed or concluded write: events to create for a
        # normal write, events to delete for a delete-only drop write.
        planned_event_count = (
            len(run.drop_task_ids) if run.drop_task_ids else len(draft.entries)
        )
        run = self._transition(run, Sig.CALENDAR_WRITE_STARTED)
        try:
            if run.drop_task_ids:
                # Delete-only write for a drop: remove the dropped tasks' events,
                # leaving survivor events in place (completion/drop memory).
                result = env.write_manager.approve_and_remove(
                    approval_event_id=approval_event_id,
                    draft=draft,
                    removed_task_ids=run.drop_task_ids,
                    target_calendar_id=target_calendar_id,
                )
            else:
                result = env.write_manager.approve_and_write(
                    approval_event_id=approval_event_id,
                    draft=draft,
                    target_calendar_id=target_calendar_id,
                    task_titles=self._task_titles_for(user_id, draft.plan_version),
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
                planned_event_count=planned_event_count,
                written_task_ids=[],
                verified_task_ids=[],
                failed_task_ids=[],
                mapping_status_by_task={},
                # Operator diagnosability: domain-error messages are typed
                # prose (never raw calendar content or secrets), so the text
                # is safe to surface alongside the reason_code.
                error=str(exc),
            )
        return self._conclude_write(
            user_id, run, result, planned_event_count=planned_event_count
        )

    def _conclude_write(
        self,
        user_id: str,
        run: RunRecord,
        result: WriteResult,
        *,
        planned_event_count: int,
    ) -> WriteCycleResult:
        """Shared outcome sequencing for ``write`` and ``retry_write``.

        Emits the success/verification-failed/failed transitions around the
        manager's ``WriteResult``, records the manager's op id on the run
        (``write_op_id``) so recovery can find the mappings later, and builds
        the operator-facing summary. ``planned_event_count`` is the caller's
        planned side-effect count (draft entries, or dropped ids on a drop
        write) — it must be carried on every outcome so the verify surface
        can render "N / M" truthfully after failures and retries.
        """
        env = self._env
        # A delete-only drop write has no created events to verify: its success
        # IS the verification (the dropped events are gone).
        verified = result.status is WriteStatus.SUCCESS and (
            bool(run.drop_task_ids)
            or (result.verification is not None and result.verification.all_verified)
        )
        if verified:
            # Clear any failure reason from a prior attempt: a run that
            # recovered via retry_write must not read as still-failed.
            run = self._transition(
                run,
                Sig.CALENDAR_WRITE_SUCCEEDED,
                write_op_id=result.run_id,
                reason_code=None,
            )
            self._activate_plan(user_id, run)
            run = self._transition(run, Sig.PLAN_ACTIVATED)
        elif result.status is WriteStatus.SUCCESS:
            run = self._transition(
                run,
                Sig.CALENDAR_VERIFICATION_FAILED,
                reason_code=ReasonCode.CALENDAR_VERIFICATION_FAILED,
                write_op_id=result.run_id,
            )
        else:
            run = self._transition(
                run,
                Sig.CALENDAR_WRITE_FAILED,
                reason_code=result.reason_code,
                write_op_id=result.run_id,
            )

        mappings = (
            # A drop write updates the dropped tasks' mappings under their
            # ORIGINAL run, not ``result.run_id`` (a fresh op id), so
            # ``list_for_run(result.run_id)`` would be empty — surface their
            # post-write status from the result's own records instead.
            list(result.written_mappings)
            if run.drop_task_ids
            else (
                env.mapping_store.list_for_run(result.run_id)
                if result.run_id is not None
                else []
            )
        )
        verification = result.verification
        return WriteCycleResult(
            run_id=run.run_id,
            user_id=user_id,
            state=run.state,
            dry_run=False,
            write_status=result.status.value,
            reason_code=run.reason_code,
            planned_event_count=planned_event_count,
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

    def rollback(
        self,
        user_id: str,
        *,
        run_id: str | None = None,
        target_calendar_id: str = DEFAULT_TARGET_CALENDAR_ID,
        dry_run: bool = False,
    ) -> RollbackCycleResult:
        """Roll back a failed calendar write: delete the events it created.

        Only valid from ``CALENDAR_WRITE_FAILED_STATE``. ``dry_run`` reports
        the would-delete count (for the confirmation dialog) without touching
        the calendar. A complete rollback exits to ``ERROR_REQUIRES_USER``;
        a partial one stays in the failure state so recovery can be retried —
        a partial rollback must never read as resolved.
        """
        env = self._env
        run = self._require_run(user_id, run_id, expected=S.CALENDAR_WRITE_FAILED_STATE)
        if run.drop_task_ids:
            raise CycleError(
                "a failed drop write has no rollback path (delete-only writes "
                "create no events); build a new plan or re-request the drop"
            )
        write_op_id = run.write_op_id
        if write_op_id is None:
            raise CycleError(
                "run has no recorded calendar write operation to roll back "
                "(the write failed before any event was created); build a new plan"
            )
        rollbackable = [
            m
            for m in env.mapping_store.list_for_run(write_op_id)
            if m.calendar_write_status
            in (
                CalendarWriteStatus.WRITTEN,
                CalendarWriteStatus.VERIFIED,
                CalendarWriteStatus.VERIFICATION_FAILED,
            )
        ]
        if dry_run:
            return RollbackCycleResult(
                run_id=run.run_id,
                user_id=user_id,
                state=run.state,
                dry_run=True,
                rollbackable_event_count=len(rollbackable),
            )

        run = self._transition(run, Sig.CALENDAR_ROLLBACK_REQUESTED)
        try:
            result = env.write_manager.rollback(
                run_id=write_op_id, target_calendar_id=target_calendar_id
            )
        except AgenticCalendarError as exc:
            run = self._transition(
                run,
                Sig.CALENDAR_ROLLBACK_FAILED,
                reason_code=ReasonCode.CALENDAR_ROLLBACK_FAILED,
            )
            return RollbackCycleResult(
                run_id=run.run_id,
                user_id=user_id,
                state=run.state,
                dry_run=False,
                rollbackable_event_count=len(rollbackable),
                fully_rolled_back=False,
                reason_code=run.reason_code,
                error=str(exc),
            )
        if result.fully_rolled_back:
            # Keep the original write-failure reason_code on the record: the
            # ERROR_REQUIRES_USER surface explains WHY the run ended here.
            run = self._transition(run, Sig.CALENDAR_ROLLBACK_COMPLETED)
        else:
            run = self._transition(
                run,
                Sig.CALENDAR_ROLLBACK_FAILED,
                reason_code=result.reason_code,
            )
        return RollbackCycleResult(
            run_id=run.run_id,
            user_id=user_id,
            state=run.state,
            dry_run=False,
            rollbackable_event_count=len(rollbackable),
            deleted_event_ids=list(result.deleted_event_ids),
            failed_event_ids=list(result.failed_event_ids),
            fully_rolled_back=result.fully_rolled_back,
            reason_code=run.reason_code,
        )

    def retry_write(
        self,
        user_id: str,
        *,
        run_id: str | None = None,
        target_calendar_id: str = DEFAULT_TARGET_CALENDAR_ID,
    ) -> WriteCycleResult:
        """Retry a failed calendar write, creating only the missing events.

        Only valid from ``CALENDAR_WRITE_FAILED_STATE``. When the failed write
        left mappings behind (mid-write crash, verification failure), this runs
        the manager's ``reconcile_after_crash`` — which re-runs the
        ``approved_payload_hash`` recheck and creates only confirmed-missing
        events. When the write failed before creating anything (pre-write
        abort), it falls back to a full ``approve_and_write``; the hash recheck
        gates that path too, so axiom 06 holds on every retry.
        """
        env = self._env
        run = self._require_run(user_id, run_id, expected=S.CALENDAR_WRITE_FAILED_STATE)
        if run.drop_task_ids:
            raise CycleError(
                "a failed drop write has no retry path (delete-only writes "
                "create no events); build a new plan or re-request the drop"
            )
        approval_event_id = run.approval_event_id
        if approval_event_id is None or run.draft_schedule_id is None:
            raise CycleError("run is missing approval/draft identifiers")
        draft = env.state.get_draft(run.draft_schedule_id)
        if draft is None:
            raise CycleError(f"draft {run.draft_schedule_id!r} not found")
        # Drop writes were rejected above, so the planned count is always the
        # approved draft's full entry set — what a completed retry must have
        # on the calendar, regardless of how many events this pass creates.
        planned_event_count = len(draft.entries)

        write_op_id = run.write_op_id
        if write_op_id is not None and not env.mapping_store.list_for_run(write_op_id):
            write_op_id = None
        run = self._transition(run, Sig.CALENDAR_WRITE_RETRY_REQUESTED)
        # Both retry paths carry the title map — a retried write must produce
        # the same properly-titled events as a first-attempt write.
        task_titles = self._task_titles_for(user_id, draft.plan_version)
        try:
            if write_op_id is not None:
                result = env.write_manager.reconcile_after_crash(
                    approval_event_id=approval_event_id,
                    draft=draft,
                    run_id=write_op_id,
                    target_calendar_id=target_calendar_id,
                    task_titles=task_titles,
                )
            else:
                # Nothing was ever written: a fresh full write is the honest
                # retry (a missing-events reconcile over zero mappings would
                # no-op and falsely report success).
                result = env.write_manager.approve_and_write(
                    approval_event_id=approval_event_id,
                    draft=draft,
                    target_calendar_id=target_calendar_id,
                    task_titles=task_titles,
                )
        except AgenticCalendarError as exc:
            reason: ReasonCode = (
                getattr(exc, "reason_code", None) or ReasonCode.CALENDAR_WRITE_FAILED
            )
            run = self._transition(run, Sig.CALENDAR_WRITE_FAILED, reason_code=reason)
            return WriteCycleResult(
                run_id=run.run_id,
                user_id=user_id,
                state=run.state,
                dry_run=False,
                write_status="failed",
                reason_code=run.reason_code,
                planned_event_count=planned_event_count,
                written_task_ids=[],
                verified_task_ids=[],
                failed_task_ids=[],
                mapping_status_by_task={},
                error=str(exc),
            )
        return self._conclude_write(
            user_id, run, result, planned_event_count=planned_event_count
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
        # Mirror completions into durable completion/drop memory before the
        # terminal-success check, so the final completing ingest is recorded too.
        # Idempotent; the scheduler projection + advisory check read it.
        self._mirror_completed_dispositions(user_id, active.plan_version, completed_ids)
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
            self._drift_input(onboarding, run, active, events)
        )
        reflection = (
            env.nodes.reflection.run(
                run_id=run.run_id,
                drift_events=drift_events,
                completion_rate=completion_rate(events) if events else None,
                # D2 continuity: the last few persisted reflections, read
                # BEFORE this one is persisted below, so the note builds on
                # what the product already told the user. Advisory prose only.
                prior_reflections=self._recent_reflections(user_id),
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

        if reflection is not None:
            # Persist AFTER the transitions so the copy carries the run's
            # final typed reason_code. Durable memory: the Week banner and the
            # reflection history read this back; the sentence the product
            # already wrote is no longer discarded with the response.
            self._persist_prose(
                run,
                ProseAttachmentKind.REFLECTION,
                summary=reflection.summary,
                detail=reflection.detail,
            )
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

    def _drift_input(
        self,
        onboarding: OnboardingRecord,
        run: RunRecord,
        active: PlanVersion,
        events: Sequence[TelemetryEvent],
    ) -> DriftInput:
        """Assemble the FULL classifier input from stored facts (UX pass B4).

        ingest used to pass ``plan`` + ``events`` only, so four of the nine
        deterministic drift rules could never fire in production (their
        optional inputs were only ever supplied by the debug CLI). Every input
        below is caller-derived observable behavior; the classifier itself
        stays untouched — axiom 07's determinism is upheld by feeding it, not
        changing it.

        * ``weekly_cycles`` — scheduled vs completed minutes per fully elapsed
          local calendar week, from the draft entries + telemetry.
        * ``fragmentation`` — free time over the next 7 days inside the user's
          scheduling window (policy day bounds minus remaining draft entries).
        * ``external_conflict_task_ids`` — tasks whose events the user deleted
          on the external calendar (EVENT_DELETED dispositions). Surfacing +
          replan proposal only; never a completion/drop (axiom 06 stance).
          Reconcile-rejected adoptions are not persisted today, so deletions —
          the loudest external signal — are the sole source.
        * ``declined_interventions`` / sponsor fields — stale unanswered
          recommitment asks and recent sponsor revocations / sent reports.
        """
        env = self._env
        user_id = onboarding.user_id
        plan = active.plan
        now = env.clock.now()
        tz = onboarding.tzinfo()
        now_local = now.astimezone(tz)
        durations = {t.task_id: t.estimated_duration_min for t in plan.tasks}

        entries: tuple[DraftScheduleEntry, ...] = ()
        if run.draft_schedule_id is not None:
            draft = env.state.get_draft(run.draft_schedule_id)
            if draft is not None:
                entries = tuple(draft.entries)

        # --- weekly capacity cycles (fully elapsed local weeks) -----------
        completed_min_by_task: dict[str, int] = {}
        for e in events:
            if e.completed:
                completed_min_by_task[e.task_id] = (
                    e.actual_duration_min or e.scheduled_duration_min
                )
        week_tasks: dict[date, set[str]] = {}
        for entry in entries:
            local_end = entry.end.astimezone(tz).date()
            monday = local_end - timedelta(days=local_end.weekday())
            week_tasks.setdefault(monday, set()).add(entry.task_id)
        cycles: list[WeeklyCapacity] = []
        for monday in sorted(week_tasks):
            week_over = datetime.combine(monday + timedelta(days=7), time(0), tzinfo=tz)
            if week_over > now_local:
                continue  # only fully elapsed weeks are assessable
            task_ids = week_tasks[monday]
            cycles.append(
                WeeklyCapacity(
                    scheduled_min=sum(durations.get(tid, 0) for tid in task_ids),
                    completed_min=sum(
                        completed_min_by_task.get(tid, 0) for tid in task_ids
                    ),
                )
            )

        # --- fragmentation: free time in the next 7 days' window ----------
        fragmentation = self._fragmentation_signal(onboarding, entries, now_local)

        # --- external conflicts (user deletions on the real calendar) -----
        external = frozenset(self._event_deleted_ids(user_id, active.plan_version))

        # --- declined interventions + sponsor pressure ---------------------
        stale_cutoff = now - timedelta(days=RECOMMITMENT_DECLINED_AFTER_DAYS)
        declined = 0
        for request in env.recommitment_store.all_requests():
            if request.user_id != user_id:
                continue
            if env.recommitment_store.event_for_request(
                request.recommitment_request_id
            ) is not None:
                continue
            if request.requested_at <= stale_cutoff:
                declined += 1
        window_start = now - timedelta(days=SPONSOR_PRESSURE_WINDOW_DAYS)
        revoked_recent = [
            s
            for s in env.sponsor_store.list_for_user(user_id)
            if s.status is SponsorStatus.REVOKED
            and s.revoked_at is not None
            and s.revoked_at >= window_start
        ]
        declined += len(revoked_recent)
        reports_recent = sum(
            1
            for log in env.notification_log_store.list_for_user(user_id)
            if log.status is NotificationStatus.SENT
            and not log.dry_run
            and log.created_at >= window_start
        )

        return DriftInput(
            plan=plan,
            events=events,
            weekly_cycles=tuple(cycles),
            fragmentation=fragmentation,
            external_conflict_task_ids=external,
            declined_interventions=declined,
            sponsor_reports_sent_recent=reports_recent,
            sponsor_reporting_disabled=bool(revoked_recent),
        )

    def _fragmentation_signal(
        self,
        onboarding: OnboardingRecord,
        entries: Sequence[DraftScheduleEntry],
        now_local: datetime,
    ) -> FragmentationSignal:
        """Free-time facts for the upcoming week, from the schedule itself.

        Deterministic and calendar-free: the free window is the user's own
        scheduling bounds (profile day window, weekend rule) minus the
        remaining draft entries. External busy time already shaped the draft
        at scheduling time, so the draft is the best stored proxy.
        """
        policy = policy_from_user_profile(onboarding.user_profile)
        tz = now_local.tzinfo

        def _hhmm(value: str) -> time:
            hour, minute = (int(p) for p in value.split(":"))
            return time(hour, minute)

        window_open = _hhmm(policy.no_events_before)
        window_close = _hhmm(policy.no_events_after)
        total_free = 0
        largest_free = 0
        for offset in range(7):
            day = now_local.date() + timedelta(days=offset)
            if not policy.allow_weekends and day.weekday() >= 5:
                continue
            day_start = datetime.combine(day, window_open, tzinfo=tz)
            day_end = datetime.combine(day, window_close, tzinfo=tz)
            if offset == 0:
                day_start = max(day_start, now_local)
            if day_end <= day_start:
                continue
            busy = sorted(
                (
                    max(e.start.astimezone(tz), day_start),
                    min(e.end.astimezone(tz), day_end),
                )
                for e in entries
                if e.end.astimezone(tz) > day_start and e.start.astimezone(tz) < day_end
            )
            cursor = day_start
            for busy_start, busy_end in busy:
                if busy_start > cursor:
                    gap = int((busy_start - cursor).total_seconds() // 60)
                    total_free += gap
                    largest_free = max(largest_free, gap)
                cursor = max(cursor, busy_end)
            if day_end > cursor:
                gap = int((day_end - cursor).total_seconds() // 60)
                total_free += gap
                largest_free = max(largest_free, gap)
        return FragmentationSignal(
            total_free_min=total_free, largest_free_block_min=largest_free
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
        # Reason-aware resume (B5): a parked run surfaces the prose the
        # product already generated for it, so returning users see WHY —
        # not a bare reason code. Read-only; the prose store is never
        # consulted for routing.
        explanation: UserExplanation | None = None
        reflection: ReflectionSummary | None = None
        if run is not None and run.state in (
            S.ERROR_REQUIRES_USER,
            S.CALENDAR_WRITE_FAILED_STATE,
        ):
            record = env.prose_store.latest_for_run(
                run.run_id, kind=ProseAttachmentKind.EXPLANATION
            )
            if record is not None:
                explanation = UserExplanation(
                    summary=record.summary, detail=list(record.detail)
                )
        if run is not None and run.state in (S.REPLAN_REQUIRED, S.DRIFT_DETECTED):
            record = env.prose_store.latest_for_run(
                run.run_id, kind=ProseAttachmentKind.REFLECTION
            )
            if record is not None:
                reflection = ReflectionSummary(
                    summary=record.summary, detail=list(record.detail)
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
            recovery_mode_pending_user_choice=(
                run is not None
                and run.state is S.REPLAN_REQUIRED
                and run.replan_kind is ReplanKind.RECOVERY
                and run.recovery_mode is None
            ),
            explanation=explanation,
            reflection=reflection,
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
        deleted_task_ids: list[str] = []
        plan_diff: PlanDiffView | None = None
        if run is not None and run.draft_schedule_id is not None:
            draft = env.state.get_draft(run.draft_schedule_id)
            if draft is not None:
                payload_hash = canonical_payload_hash(draft, HASH_CANONICALIZATION_VERSION)
                plan = env.plan_store.get(user_id, draft.plan_version)
                if plan is not None:
                    task_titles = {task.task_id: task.title for task in plan.plan.tasks}
                    plan_diff = self._plan_diff_view(user_id, plan)
                deleted_task_ids = sorted(
                    self._event_deleted_ids(user_id, draft.plan_version)
                )
        return DraftView(
            draft=draft,
            payload_hash=payload_hash,
            hash_canonicalization_version=HASH_CANONICALIZATION_VERSION,
            free_busy=[dict(interval) for interval in (free_busy or [])],
            task_titles=task_titles,
            deleted_task_ids=deleted_task_ids,
            plan_diff=plan_diff,
        )

    def _plan_diff_view(
        self, user_id: str, plan: PlanVersion
    ) -> PlanDiffView | None:
        """The compact content delta vs ``plan``'s parent, or ``None`` (D4).

        Recomputed from the two persisted plan versions on every fetch — the
        diff is a pure function of stored plans (``planning/diff.py``), so a
        read projection derives it instead of persisting a copy. ``None`` for
        a fresh propose (no parent) or when the parent version is unknown.
        """
        if plan.parent_plan_version is None:
            return None
        parent = self._env.plan_store.get(user_id, plan.parent_plan_version)
        if parent is None:
            return None
        content: PlanContentDiff = diff_plan_content(parent.plan, plan.plan)
        return PlanDiffView(
            from_plan_version=content.from_plan_version,
            to_plan_version=content.to_plan_version,
            tasks_added=len(content.added_ids),
            tasks_removed=len(content.removed_ids),
            tasks_changed=len(content.changed_ids),
            tasks_preserved=len(content.preserved_ids),
            net_load_change_min=content.summary.net_weekly_load_change_min,
            changes=list(content.change_lines),
        )

    def today(self, user_id: str) -> TodayResult:
        """The active plan's scheduled tasks as structured rows (tz-aware
        datetimes; the client localizes). ``due`` marks a block whose time has
        passed; ``reported`` marks one that already has telemetry; ``deleted``
        marks one whose calendar event the user deleted externally (the task
        itself is still planned — never rendered as completed)."""
        env = self._env
        onboarding = env.state.get_onboarding(user_id)
        timezone = onboarding.timezone if onboarding is not None else None
        draft = self._active_draft(user_id)
        active = env.plan_store.get_active(user_id)
        if draft is None or active is None:
            return TodayResult(timezone=timezone, tasks=[])
        now = env.clock.now()
        tasks = {task.task_id: task for task in active.plan.tasks}
        deleted_ids = self._event_deleted_ids(user_id, active.plan_version)
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
                    deleted=entry.task_id in deleted_ids,
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
            inbound_calendar_sync_enabled=(
                onboarding.inbound_calendar_sync_enabled if onboarding is not None else False
            ),
        )

    def pathways_view(
        self, user_id: str, *, track: str | None = None
    ) -> PathwaysResult:
        """Registry cards for a track plus the user's deterministic coverage (NP-D).

        ``track`` is the optional query-param filter; an unknown value falls back
        to the track resolved from the profile's ``target_role`` (and if that is
        also unresolvable, every pathway is shown). Fit counts and slot states
        are computed by the ``narrative/`` kernel over the *stored* profile — no
        LLM participates — and the cards are ordered by ``filled_slots``
        descending, ties broken by registry order (a stable sort).
        """
        profile = self._require_onboarding(user_id).user_profile
        return self._pathways_result(profile, track)

    def preview_pathways(
        self, user_id: str, payload: Mapping[str, Any]
    ) -> PathwaysResult:
        """Pathway cards + coverage over a *draft* profile - persistence-free (NP-E).

        The onboarding wizard's "Your story" step needs live slot coverage before
        the profile is saved, so this mirrors :meth:`extract_resume`'s
        persistence-free posture: the body's ``user_profile`` is validated (with
        ``user_id`` forced to the acting user - the onboard trust boundary) and run
        through the same :meth:`_pathways_result` the persisted
        :meth:`pathways_view` uses, so a draft and a saved profile with identical
        evidence produce byte-identical cards. Nothing is stored; the only profile
        write path stays :meth:`onboard`. ``payload`` keys: ``user_profile``
        (required), ``track`` (optional filter).
        """
        raw = payload.get("user_profile")
        profile_dict = dict(raw) if isinstance(raw, Mapping) else {}
        profile = UserProfile.model_validate({**profile_dict, "user_id": user_id})
        track = payload.get("track")
        return self._pathways_result(profile, track if isinstance(track, str) else None)

    def _pathways_result(
        self, profile: UserProfile, track: str | None
    ) -> PathwaysResult:
        """The registry cards + per-profile coverage, shared by the persisted and
        draft-preview surfaces so both agree exactly (NP-E)."""
        resolved_track = self._resolve_pathways_track(track, profile)
        templates = (
            pathways_for_track(resolved_track)
            if resolved_track is not None
            else list_pathways()
        )
        selection = profile.pathway_selection
        selected_id = selection.pathway_id if selection is not None else None
        _template, version_mismatch = self._resolve_selection_template(profile)
        cards = [self._pathway_card(profile, t, selected_id) for t in templates]
        cards.sort(key=lambda c: c.filled_slots, reverse=True)
        return PathwaysResult(
            track=resolved_track,
            registry_version=PATHWAY_REGISTRY_VERSION,
            selected_pathway_id=selected_id,
            version_mismatch=version_mismatch,
            cards=cards,
        )

    def evidence_vocabulary_view(
        self, user_id: str, *, role: str | None = None
    ) -> EvidenceVocabularyResult:
        """The closed evidence-tagging vocabularies for the UI dropdowns (NP-E).

        ``kinds`` is the fixed :class:`EvidenceKind` enum; ``themes`` is the
        registry's per-track slice. The track resolves from ``role`` when given
        (the wizard passes the not-yet-saved ``target_role`` - this endpoint does
        not require onboarding), else from the stored profile's ``target_role``
        when the user is onboarded, else ``None`` (empty theme slice). Registry
        literals only - the same closed sets the intake node is bound to.
        """
        resolved_track: CareerTrack | None = None
        if role is not None and role.strip():
            resolved_track = resolve_track(role)
        else:
            onboarding = self._env.state.get_onboarding(user_id)
            if onboarding is not None:
                resolved_track = resolve_track(onboarding.user_profile.target_role)
        themes = (
            list(theme_vocabulary(resolved_track))
            if resolved_track is not None
            else []
        )
        return EvidenceVocabularyResult(
            track=resolved_track,
            registry_version=PATHWAY_REGISTRY_VERSION,
            kinds=list(EvidenceKind),
            themes=themes,
        )

    def select_pathway(
        self,
        user_id: str,
        *,
        pathway_id: str,
        slot_overrides: Sequence[Mapping[str, Any]] = (),
    ) -> MeResult:
        """Set (or change) the profile's pathway selection - a targeted mutation (NP-E).

        Unlike re-running :meth:`onboard`, this touches only ``pathway_selection``:
        the accountability contract (motivation profile), ``created_at``, the
        inbound-calendar-sync opt-in, evidence, and every other profile field are
        preserved byte-for-byte - the profile-update policy row "Pathway changed →
        Invalidate Accountability Contract? No", which a full re-onboard (whose
        payload cannot carry the motivation profile back) could not honor. The
        selection always pins the *current* registry version. Registry membership
        is checked (``_reject_invalid_selection``); a bad ``pathway_id`` or override
        slot is a command-precondition failure (``CycleError`` → HTTP 409). When
        the ``pathway_id`` changes vs the stored selection, the syllabus, tasks,
        and schedule are invalidated exactly as :meth:`onboard` does.
        """
        onboarding = self._require_onboarding(user_id)
        prior_profile = onboarding.user_profile
        selection = PathwaySelection.model_validate(
            {
                "pathway_id": pathway_id,
                "pathway_registry_version": PATHWAY_REGISTRY_VERSION,
                "selected_at": self._env.clock.now(),
                "slot_overrides": list(slot_overrides),
            }
        )
        new_profile = UserProfile.model_validate(
            prior_profile.model_dump(mode="json")
            | {"pathway_selection": selection.model_dump(mode="json")}
        )
        rejection = self._reject_invalid_selection(new_profile)
        if rejection is not None:
            _reason, detail = rejection
            raise CycleError(detail)
        record = OnboardingRecord.model_validate(
            onboarding.model_dump()
            | {
                "user_profile": new_profile.model_dump(mode="json"),
                "updated_at": self._env.clock.now(),
            }
        )
        if self._selection_id(prior_profile) != self._selection_id(new_profile):
            self._invalidate_for_pathway_change(user_id)
        self._env.state.save_onboarding(record)
        return self.me(user_id)

    def _resolve_pathways_track(
        self, track: str | None, profile: UserProfile
    ) -> CareerTrack | None:
        """Pick the track to draw cards for: an explicit valid query param wins,
        else the track resolved from the profile's ``target_role`` (possibly
        ``None`` when nothing resolves — the caller then shows every pathway)."""
        if track is not None:
            try:
                return CareerTrack(track)
            except ValueError:
                pass  # unknown track string: fall back to the profile's track
        return resolve_track(profile.target_role)

    def _pathway_card(
        self, profile: UserProfile, template: PathwayTemplate, selected_id: str | None
    ) -> PathwayCard:
        """One card: kernel coverage over ``template`` for ``profile``'s evidence."""
        coverage = slot_coverage(profile, template)
        slots = [
            PathwaySlotView(
                slot_id=cover.slot_id,
                title=slot.title,
                state=cover.state,
                matched_item_indices=list(cover.matched_item_indices),
            )
            for slot, cover in zip(template.evidence_slots, coverage, strict=True)
        ]
        return PathwayCard(
            pathway_id=template.pathway_id,
            display_name=template.display_name,
            spine=template.spine,
            audience_note=template.audience_note,
            career_track=template.career_track,
            filled_slots=sum(1 for c in coverage if c.state is SlotState.FILLED),
            total_slots=len(template.evidence_slots),
            slots=slots,
            selected=template.pathway_id == selected_id,
        )

    # ------------------------------------------------------------------ #
    # story-layer LLM prose (NP-F) — fit notes + story summary
    # ------------------------------------------------------------------ #
    #
    # Both targets live inside the UserFacingExplanationNode (the fifth-and-only
    # explanation node; no new node class per 03-llm-surfaces). They DECORATE
    # the deterministic ``narrative/`` coverage the kernel already computed:
    # the structured input is that coverage (filled/open slot titles + matched
    # evidence titles), never the raw résumé, so fit/gaps stay 100% deterministic
    # (axiom 00) and the prose only explains them. Neither call persists prose —
    # the client holds it for the session; only the append-only LLM call log is
    # written (required per axiom 22).

    #: The batched fit-note call covers the top-N cards by the kernel's ranking
    #: (03-llm-surfaces: "one call returning notes for the top N cards, N <= 4").
    _FIT_NOTE_MAX_CARDS = 4

    def _card_fit_slots(
        self, profile: UserProfile, card: PathwayCard
    ) -> tuple[FitNoteSlot, ...]:
        """Project a card's kernel coverage into the prose node's slot shape:
        the pillar title, its opaque state label, and the confirmed evidence
        titles the kernel matched to it (so the prose can name *why* a pillar is
        filled without ever seeing the raw résumé)."""
        titles = [item.title for item in profile.experience]
        return tuple(
            FitNoteSlot(
                title=slot.title,
                state=slot.state.value,
                matched_titles=tuple(
                    titles[i] for i in slot.matched_item_indices if 0 <= i < len(titles)
                ),
            )
            for slot in card.slots
        )

    def pathway_fit_notes(
        self, user_id: str, payload: Mapping[str, Any]
    ) -> FitNotesResult:
        """One batched LLM fit note per top pathway card (NP-F) — display-only.

        Mirrors :meth:`preview_pathways`'s draft-or-saved posture: with a
        ``user_profile`` in the body the wizard's not-yet-saved evidence is used
        (persistence-free, onboarding not required); without it the stored
        profile is read. The cards are ranked deterministically by
        :meth:`_pathways_result` (no LLM), the top ``_FIT_NOTE_MAX_CARDS`` are
        put to the explanation node in one call, and the notes come back keyed by
        ``pathway_id``. A node failure returns a typed ``status="failed"`` result
        (HTTP 200) so the UI simply shows no notes; the cards are never blocked
        on this call. ``payload`` keys: ``user_profile`` (optional draft),
        ``track`` (optional filter)."""
        raw = payload.get("user_profile")
        if isinstance(raw, Mapping):
            profile = UserProfile.model_validate({**dict(raw), "user_id": user_id})
        else:
            profile = self._require_onboarding(user_id).user_profile
        track = payload.get("track")
        result = self._pathways_result(
            profile, track if isinstance(track, str) else None
        )
        top = result.cards[: self._FIT_NOTE_MAX_CARDS]
        if not top:
            return FitNotesResult(
                registry_version=result.registry_version, notes={}
            )
        requests = tuple(
            FitNoteRequest(
                pathway_id=card.pathway_id,
                display_name=card.display_name,
                spine=card.spine,
                audience_note=card.audience_note,
                slots=self._card_fit_slots(profile, card),
            )
            for card in top
        )
        run_id = f"story-{self._env.id_generator.new_id('run')}"
        try:
            notes = self._env.nodes.explanation.run_fit_notes(
                run_id=run_id, requests=requests
            )
        except LLMNodeError as exc:
            reason = getattr(exc, "reason_code", None) or ReasonCode.LLM_CALL_FAILED
            return FitNotesResult(
                status="failed",
                registry_version=result.registry_version,
                reason_code=reason,
                detail=str(exc),
            )
        return FitNotesResult(
            registry_version=result.registry_version,
            notes={note.pathway_id: note.note for note in notes.notes},
        )

    def story_summary(self, user_id: str) -> StorySummaryResult:
        """User-initiated "where your package stands" summary (NP-F) — display-only.

        Requires a live pathway selection (a stale-pinned or missing selection is
        a command-precondition failure → HTTP 409; the Story panel only offers
        this in the selected branch). The input is the selected pathway's
        deterministic slot coverage; a node failure is a typed
        ``status="failed"`` result (HTTP 200). Nothing is persisted."""
        profile = self._require_onboarding(user_id).user_profile
        template, version_mismatch = self._resolve_selection_template(profile)
        if template is None:
            hint = (
                " (its pinned registry version is stale — re-confirm it first)"
                if version_mismatch
                else ""
            )
            raise CycleError(
                f"user {user_id!r} has no live pathway selection; choose a pathway "
                f"before requesting a story summary{hint}"
            )
        card = self._pathway_card(profile, template, template.pathway_id)
        request = StorySummaryRequest(
            pathway_id=template.pathway_id,
            display_name=template.display_name,
            spine=template.spine,
            slots=self._card_fit_slots(profile, card),
        )
        run_id = f"story-{self._env.id_generator.new_id('run')}"
        try:
            summary = self._env.nodes.explanation.run_story_summary(
                run_id=run_id, request=request
            )
        except LLMNodeError as exc:
            reason = getattr(exc, "reason_code", None) or ReasonCode.LLM_CALL_FAILED
            return StorySummaryResult(status="failed", reason_code=reason)
        return StorySummaryResult(
            summary=summary.summary, detail=list(summary.detail)
        )

    def mark_evidence(
        self,
        user_id: str,
        *,
        title: str,
        organization: str | None = None,
        summary: str | None = None,
        kind: EvidenceKind = EvidenceKind.WORK,
        theme_tags: Sequence[str] = (),
    ) -> MeResult:
        """Append one confirmed evidence item to the profile (NP-D).

        A plain profile edit: no LLM, and - unlike a pathway change - no
        invalidation. Evidence is a pathway-independent fact; coverage recomputes
        on read (profile-update policy: "Evidence item added/edited/marked" is
        No/No/No/No), and a filled slot merely makes a planned module redundant,
        which the next regular replan absorbs. ``theme_tags`` stay closed to the
        track's registry vocabulary - they are join keys for the ``narrative/``
        kernel, not free text - with an empty list always allowed; the list cap
        (20) is contract-enforced when the profile is rebuilt.
        """
        onboarding = self._require_onboarding(user_id)
        profile = onboarding.user_profile
        tags = list(theme_tags)
        track = resolve_track(profile.target_role)
        if track is not None:
            off_vocab = sorted(
                {t for t in tags if not is_theme_in_vocabulary(track, t)}
            )
            if off_vocab:
                raise CycleError(
                    f"theme_tags not in the {track.value} theme vocabulary: "
                    f"{off_vocab}"
                )
        profile_dump = profile.model_dump(mode="json")
        new_item = {
            "title": title,
            "organization": organization,
            "summary": summary,
            "kind": kind.value,
            "theme_tags": tags,
        }
        new_profile = UserProfile.model_validate(
            profile_dump | {"experience": [*profile_dump["experience"], new_item]}
        )
        record = OnboardingRecord.model_validate(
            onboarding.model_dump()
            | {
                "user_profile": new_profile.model_dump(mode="json"),
                "updated_at": self._env.clock.now(),
            }
        )
        self._env.state.save_onboarding(record)
        return self.me(user_id)

    def inbound_calendar_sync_enabled(self, user_id: str) -> bool:
        """Whether the user opted in to inbound calendar reconciliation (off until
        they do; the reconcile trigger resolves this and passes it to
        :meth:`reconcile`)."""
        onboarding = self._env.state.get_onboarding(user_id)
        return onboarding is not None and onboarding.inbound_calendar_sync_enabled

    def set_inbound_calendar_sync(self, user_id: str, *, enabled: bool) -> bool:
        """Set the user's inbound-calendar-sync opt-in; returns the new value.

        Rebuilds the frozen onboarding record (re-running its validators) with a
        fresh ``updated_at``; the original ``created_at`` is preserved.
        """
        env = self._env
        onboarding = self._require_onboarding(user_id)
        updated = OnboardingRecord.model_validate(
            onboarding.model_dump()
            | {
                "inbound_calendar_sync_enabled": enabled,
                "updated_at": env.clock.now(),
            }
        )
        env.state.save_onboarding(updated)
        return enabled

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
        open_request = self._open_recommitment_request(user_id)
        # Reflection history (D2): the coaching notes, newest first, replayed
        # for display. Read-only copy of the prose store; independent of the
        # snapshot so it survives an empty accountability state. Capped so the
        # payload stays a screenful, not the user's full archive.
        history = [
            ReflectionHistoryEntry(
                created_at=r.created_at,
                summary=r.summary,
                detail=list(r.detail),
                plan_version=r.plan_version,
            )
            for r in reversed(env.prose_store.list_for_user(user_id))
            if r.kind is ProseAttachmentKind.REFLECTION
        ][:_REFLECTION_HISTORY_LIMIT]
        return AccountabilityResult(
            has_motivation_profile=has_motivation_profile,
            checkin_status=snapshot.checkin_status.value if snapshot is not None else None,
            state=snapshot.state if snapshot is not None else None,
            decision=snapshot.decision if snapshot is not None else None,
            checkin_due=(
                snapshot is not None
                and snapshot.checkin_status in (CheckinStatus.DUE, CheckinStatus.MISSED)
            ),
            open_recommitment_request_id=(
                open_request.recommitment_request_id if open_request is not None else None
            ),
            reflection_history=history,
        )

    def _open_recommitment_request(self, user_id: str) -> RecommitmentRequest | None:
        """The newest recommitment ask this user has not answered yet."""
        env = self._env
        for request in reversed(env.recommitment_store.all_requests()):
            if request.user_id != user_id:
                continue
            if env.recommitment_store.event_for_request(request.recommitment_request_id) is None:
                return request
        return None

    def recommit(
        self,
        user_id: str,
        choice: RecommitmentChoice,
        *,
        recommitment_request_id: str | None = None,
    ) -> RecommitResult:
        """Answer the open recommitment ask (the loop-closing half of the
        nudge → recommitment flow; the ask half has always run in ingest).

        The typed choice maps deterministically onto the recovery path:
        ``revise_timeline`` → extend-timeline replan, ``revise_intensity`` →
        reduced-load replan (RECOMMITMENT_CHOICE_TO_RECOVERY_MODE). Both park
        the active run in REPLAN_REQUIRED — the draft still flows through
        review + approval; nothing changes silently. ``keep_plan`` records
        explicit re-approval; ``revise_goal`` records the intent and leaves
        profile changes to onboarding. Answer-once is store-enforced.
        """
        env = self._env
        self._require_onboarding(user_id)
        if recommitment_request_id is not None:
            request = env.recommitment_store.get_request(recommitment_request_id)
            if request is None or request.user_id != user_id:
                raise CycleError("recommitment request not found for this user")
            if env.recommitment_store.event_for_request(recommitment_request_id) is not None:
                raise CycleError("recommitment request already answered")
        else:
            maybe_request = self._open_recommitment_request(user_id)
            if maybe_request is None:
                raise CycleError("no open recommitment request to answer")
            request = maybe_request

        event = record_recommitment(
            request,
            choice,
            store=env.recommitment_store,
            clock=env.clock,
            id_generator=env.id_generator,
        )

        mapped = RECOMMITMENT_CHOICE_TO_RECOVERY_MODE.get(choice)
        run = env.state.latest_run_for_user(user_id)
        replan_required = False
        if mapped is not None and run is not None:
            if run.state is S.ACTIVE_PLAN:
                run = self._transition(
                    run,
                    Sig.RECOMMITMENT_ACCEPTED,
                    replan_kind=ReplanKind.RECOVERY,
                    recovery_mode=mapped,
                    reason_code=ReasonCode.USER_RECOMMITMENT_REQUIRED,
                )
                replan_required = True
            elif (
                run.state is S.REPLAN_REQUIRED
                and run.replan_kind is ReplanKind.RECOVERY
            ):
                # The run is already parked on the recovery path — the answer
                # resolves a pending ask-each-time choice, or OVERRIDES the
                # drift-derived mode: the user's explicit, typed choice beats
                # the heuristic mapping. Metadata only — the state doesn't
                # change, so no transition.
                run = self._save_run(run, recovery_mode=mapped)
                replan_required = True
        return RecommitResult(
            user_id=user_id,
            recommitment_request_id=request.recommitment_request_id,
            recommitment_event_id=event.recommitment_event_id,
            choice=choice,
            recovery_mode=mapped,
            replan_required=replan_required,
            state=run.state if run is not None else None,
        )

    def weekly_checkin(
        self,
        user_id: str,
        *,
        blockers: str | None = None,
        recovery_action: RecoveryAction | None = None,
    ) -> WeeklyCheckinResult:
        """Submit the weekly check-in ("How did this week go?").

        First production producer of :class:`CheckinEvent` — until it existed,
        ``evaluate_checkin`` saw an empty history and the policy engine emitted
        CHECKIN_DUE/MISSED forever. Counts are computed server-side from the
        active draft + telemetry over the trailing week in the user's timezone;
        the client contributes only optional blockers prose (stored, never a
        prompt input) and an optional recovery preference.
        """
        env = self._env
        onboarding = self._require_onboarding(user_id)
        if onboarding.motivation_profile is None:
            raise CycleError(
                "weekly check-in requires a motivation profile (accountability is opt-in)"
            )
        active = env.plan_store.get_active(user_id)
        run = env.state.latest_run_for_user(user_id)
        if active is None or run is None:
            raise CycleError("no active plan to check in on")

        now = env.clock.now()
        tz = onboarding.tzinfo()
        week_end = now.astimezone(tz).date()
        week_start = week_end - timedelta(days=6)

        entries: tuple[Any, ...] = ()
        if run.draft_schedule_id is not None:
            draft = env.state.get_draft(run.draft_schedule_id)
            if draft is not None:
                entries = draft.entries
        durations = {t.task_id: t.estimated_duration_min for t in active.plan.tasks}
        week_task_ids = {
            e.task_id
            for e in entries
            if week_start <= e.end.astimezone(tz).date() <= week_end
        }
        completed_by_task: dict[str, TelemetryEvent] = {}
        for ev in self._events_for_plan(active.plan):
            if ev.completed and ev.task_id in week_task_ids:
                completed_by_task[ev.task_id] = ev

        event = CheckinEvent(
            checkin_id=env.id_generator.new_id("weekly_checkin"),
            user_id=user_id,
            plan_id=active.plan_version,
            week_start=week_start,
            week_end=week_end,
            completed_task_count=len(completed_by_task),
            scheduled_task_count=len(week_task_ids),
            completed_minutes=sum(
                (ev.actual_duration_min or ev.scheduled_duration_min)
                for ev in completed_by_task.values()
            ),
            scheduled_minutes=sum(durations.get(tid, 0) for tid in week_task_ids),
            user_reported_blockers=blockers,
            user_selected_recovery_action=recovery_action,
            created_at=now,
        )
        env.checkin_store.append(event)

        contract = derive_accountability_contract(
            onboarding.motivation_profile, id_generator=env.id_generator, clock=env.clock
        )
        checkins = env.checkin_store.list_for_plan(user_id, active.plan_version)
        assessment = evaluate_checkin(contract, checkins, now=now, tz=tz)
        return WeeklyCheckinResult(
            user_id=user_id,
            checkin_id=event.checkin_id,
            checkin_status=assessment.status.value,
            week_start=week_start,
            week_end=week_end,
            scheduled_task_count=event.scheduled_task_count,
            completed_task_count=event.completed_task_count,
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
