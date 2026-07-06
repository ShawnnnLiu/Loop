"""Typed results every cycle operation returns.

These are the operator-facing summaries the CLI serializes. They reuse the
contract models for anything structured (unscheduled tasks, drift events)
so a typed ``reason_code`` is never flattened into prose, and they carry the
LLM prose nodes' output (reflection / explanation) as *attachments* — the
deterministic fields are always sufficient to act on without reading them.
"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from agentic_calendar.contracts.accountability_intervention import InterventionDecision
from agentic_calendar.contracts.accountability_state import AccountabilityState
from agentic_calendar.contracts.checkin_event import RecoveryAction
from agentic_calendar.contracts.draft_schedule import DraftSchedule
from agentic_calendar.contracts.drift_event import DriftEvent
from agentic_calendar.contracts.plan_diff import PlanDiff
from agentic_calendar.contracts.reason_codes import ReasonCode
from agentic_calendar.contracts.recommitment import RecommitmentChoice
from agentic_calendar.contracts.scheduler_output import RepairOption, UnscheduledTask
from agentic_calendar.contracts.threshold_change_log import ThresholdChange
from agentic_calendar.contracts.user_profile import UserProfile
from agentic_calendar.contracts.validation_result import Violation
from agentic_calendar.llm_nodes.reflection_summary import ReflectionSummary
from agentic_calendar.llm_nodes.user_facing_explanation import UserExplanation
from agentic_calendar.supervisor.state import SupervisorState

from .state import ReplanKind


class OnboardResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    user_id: str
    created: bool
    """``True`` on first onboarding, ``False`` when an existing record was updated."""
    timezone: str
    has_motivation_profile: bool


class ProposeResult(BaseModel):
    """Outcome of one propose (or replan-continuation) pipeline run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    user_id: str
    state: SupervisorState
    reason_code: ReasonCode | None = None
    plan_version: str | None = None
    parent_plan_version: str | None = None
    replan_kind: ReplanKind | None = None
    recovery_mode: RecoveryAction | None = None
    draft_schedule_id: str | None = None
    draft_payload_hash: str | None = None
    scheduled_task_count: int = 0
    unscheduled_tasks: list[UnscheduledTask] = Field(default_factory=list)
    repair_options: list[RepairOption] = Field(default_factory=list)
    violations: list[Violation] = Field(default_factory=list)
    """Typed, structured violations from a terminal validation failure (e.g.
    user-fit). Deterministic numeric facts only — clients format them into a
    specific recovery message; the typed ``reason_code`` stays the contract."""
    explanation: UserExplanation | None = None
    """LLM prose attachment (validation wording); never control-plane."""
    plan_diff: PlanDiff | None = None
    """Deterministic content diff vs the parent plan version (D4 stage 2) —
    present only when this propose continued from an existing plan (replan).
    Computed by code from the two persisted plans, never by an LLM."""


class DropResult(BaseModel):
    """Outcome of one drop request: a survivors-only DRAFT awaiting approval.

    A fresh run carries the drop to approval; the active plan stays ACTIVE until
    the drop is approved + written (a delete-only write that removes only the
    dropped events). Rejecting discards this run and leaves the active plan
    untouched.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    user_id: str
    state: SupervisorState
    plan_version: str
    parent_plan_version: str
    draft_schedule_id: str
    draft_payload_hash: str
    dropped_task_ids: list[str] = Field(default_factory=list)
    survivor_task_count: int = 0


class AdjustViolation(BaseModel):
    """One typed reason a hand-adjusted placement was refused (a hard rule)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    task_id: str
    reason_code: ReasonCode
    detail: str


class AdjustWarning(BaseModel):
    """One non-blocking advisory on an applied drag-to-adjust (ADR-0008).

    Today the only code is ``DEPENDENCY_ADVISORY`` — a move that starts before an
    unfinished prerequisite. A populated ``warnings`` with ``applied: true`` is
    informational; clients must not infer failure from it.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    task_id: str
    reason_code: ReasonCode
    detail: str


class AdjustResult(BaseModel):
    """Outcome of one drag-to-adjust on a draft awaiting approval.

    On success a new immutable draft replaces the pending one and its fresh
    canonical hash is returned. On a rejected move nothing is persisted and the
    typed ``violations`` say which placements failed and why.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    user_id: str
    state: SupervisorState
    applied: bool
    reason_code: ReasonCode | None = None
    draft_schedule_id: str | None = None
    draft_payload_hash: str | None = None
    adjusted_task_ids: list[str] = Field(default_factory=list)
    scheduled_task_count: int = 0
    violations: list[AdjustViolation] = Field(default_factory=list)
    warnings: list[AdjustWarning] = Field(default_factory=list)
    """Non-blocking advisories on an applied move (ADR-0008); empty on refusal.
    A populated list with ``applied: true`` is informational, never failure."""


class ApproveResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    user_id: str
    state: SupervisorState
    rejected: bool
    plan_version: str
    approval_event_id: str | None = None
    approved_payload_hash: str | None = None
    expires_at_iso: str | None = None


class WriteCycleResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    user_id: str
    state: SupervisorState
    dry_run: bool
    write_status: str | None = None
    reason_code: ReasonCode | None = None
    planned_event_count: int = 0
    written_task_ids: list[str] = Field(default_factory=list)
    verified_task_ids: list[str] = Field(default_factory=list)
    failed_task_ids: list[str] = Field(default_factory=list)
    mapping_status_by_task: dict[str, str] = Field(default_factory=dict)
    error: str | None = None
    """Failure detail passed through from the write manager (or the
    defense-in-depth guard) so the operator can diagnose a failed write
    beyond the bare ``reason_code``. Typed error prose only — adapters
    never embed raw calendar content or secrets. ``None`` on success."""


class RollbackCycleResult(BaseModel):
    """Outcome of a user-triggered rollback of a failed calendar write.

    ``dry_run=True`` reports what a rollback WOULD delete (the confirm-dialog
    count) without touching the calendar. A completed rollback parks the run in
    ``ERROR_REQUIRES_USER`` (the events are gone; the honest next step is a new
    plan); a partial rollback keeps the run in the failure state so the user
    can retry either recovery path.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    user_id: str
    state: SupervisorState
    dry_run: bool
    rollbackable_event_count: int
    """Events a rollback would delete (written/verified/verification-failed)."""
    deleted_event_ids: list[str] = Field(default_factory=list)
    failed_event_ids: list[str] = Field(default_factory=list)
    fully_rolled_back: bool | None = None
    """``None`` on dry-run; otherwise whether every event deletion succeeded."""
    reason_code: ReasonCode | None = None
    error: str | None = None
    """Failure detail passed through from the write manager. Typed error
    prose only — never raw calendar content. ``None`` on success/dry-run."""


class TelemetryItemOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: str
    telemetry_event_id: str | None = None
    reason_code: ReasonCode | None = None
    error: str | None = None


class IngestResult(BaseModel):
    """Outcome of one ingest: stored telemetry plus the deterministic assessment."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    user_id: str
    outcomes: list[TelemetryItemOutcome]
    ingested_count: int
    duplicate_count: int
    rejected_count: int
    run_id: str | None = None
    state: SupervisorState | None = None
    assessed: bool = False
    """``False`` when no run was in ``ACTIVE_PLAN`` — telemetry stored, nothing judged."""
    plan_completed: bool = False
    drift_events: list[DriftEvent] = Field(default_factory=list)
    reflection: ReflectionSummary | None = None
    """LLM prose attachment explaining classified drift; never control-plane."""
    accountability_action: str | None = None
    accountability_reason_code: ReasonCode | None = None
    nudge_id: str | None = None
    recommitment_request_id: str | None = None
    replan_required: bool = False
    replan_kind: ReplanKind | None = None
    recovery_mode: RecoveryAction | None = None
    recovery_mode_pending_user_choice: bool = False
    """Replan required but the motivation profile says ``ask_each_time`` —
    ``propose --recovery-mode ...`` supplies the user's choice."""


class StatusResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    user_id: str
    onboarded: bool
    timezone: str | None = None
    run_id: str | None = None
    state: SupervisorState | None = None
    reason_code: ReasonCode | None = None
    plan_version: str | None = None
    active_plan_version: str | None = None
    plan_version_count: int = 0
    draft_schedule_id: str | None = None
    approval_event_id: str | None = None
    replan_kind: ReplanKind | None = None
    recovery_mode: RecoveryAction | None = None
    recovery_mode_pending_user_choice: bool = False
    """The run is parked in REPLAN_REQUIRED on the recovery path with no
    recovery mode resolved (motivation profile says ask_each_time): ``propose``
    will 409 until the client supplies one. The SPA renders the mode picker
    from this flag."""
    explanation: UserExplanation | None = None
    """Persisted prose for a run parked in a failure state — what the product
    already told the user about WHY. Display attachment; never control-plane."""
    reflection: ReflectionSummary | None = None
    """Persisted drift reflection for a parked replan (the Week banner's
    disclosure). Display attachment; never control-plane."""
    mapping_status_by_task: dict[str, str] = Field(default_factory=dict)
    telemetry_event_count: int = 0
    nudge_count: int = 0
    checkin_count: int = 0


# --------------------------------------------------------------------------- #
# Read-projection results (F-A): JSON the SPA renders from. Like StatusResult,
# these are app-layer view models — NOT schema-exported contracts — and reuse
# the registered contracts (DraftSchedule, UserProfile, …) for anything
# structured. Times stay as tz-aware datetimes (``model_dump(mode="json")``
# serializes them to ISO-8601); the client localizes them.
# --------------------------------------------------------------------------- #


class PlanDiffView(BaseModel):
    """Compact deterministic delta between the pending draft's plan and its
    parent plan version (D4 stage 2) — what the review/approval banners render
    ("3 changed, 14 preserved"). Recomputed read-only from the two persisted
    plan versions on every fetch (``planning/diff.py``), never stored and
    never LLM-authored. The four counts partition the tasks: a task counts as
    preserved only when its full content is identical."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    from_plan_version: str
    to_plan_version: str
    tasks_added: int = Field(ge=0)
    tasks_removed: int = Field(ge=0)
    tasks_changed: int = Field(ge=0)
    tasks_preserved: int = Field(ge=0)
    net_load_change_min: int
    """Plan-wide net minutes delta; positive means more total work."""
    changes: list[str] = Field(default_factory=list)
    """One deterministic line per removed/changed/added task, in that order."""


class DraftView(BaseModel):
    """The pending draft the review/approval screens render, with the canonical
    hash the user approves and the imported busy windows the grid draws as
    fixed. ``free_busy`` is supplied by the web layer (it needs the per-user
    calendar credential); empty when the calendar can't be read."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    draft: DraftSchedule | None = None
    payload_hash: str | None = None
    hash_canonicalization_version: str
    free_busy: list[dict[str, str]] = Field(default_factory=list)
    task_titles: dict[str, str] = Field(default_factory=dict)
    """task_id -> title for the draft's plan version, so the grid can label
    blocks (a draft entry carries only the task_id)."""
    deleted_task_ids: list[str] = Field(default_factory=list)
    """Sorted task_ids whose calendar event the user deleted externally
    (``event_deleted`` dispositions for the draft's plan version). The grid
    renders these as a distinct "deleted from calendar" state — never as the
    written checkmark, and never as completion (the task is still planned)."""
    plan_diff: PlanDiffView | None = None
    """Content delta vs the parent plan version — present for any draft with
    a parent (replan, recalibration, drop); ``None`` on a fresh propose."""


class TodayTask(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    task_id: str
    title: str
    category: str
    required_focus_level: str
    start: datetime
    end: datetime
    due: bool
    """True once the block has ended — only a due task can be checked in."""
    reported: bool
    """True once a telemetry event exists for the task (idempotency)."""
    deleted: bool
    """True when the task's calendar event was deleted externally
    (``event_deleted`` disposition). The task itself is still planned and can
    still be checked in — a deleted event is not a completed task."""


class TodayResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    timezone: str | None = None
    tasks: list[TodayTask] = Field(default_factory=list)


class ThresholdFieldView(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    value: float | int | bool
    status: str
    """``default`` or ``overridden`` — serving truth vs. the code default."""


class ThresholdSectionView(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    fields: list[ThresholdFieldView]


class ThresholdsResult(BaseModel):
    """The effective deterministic tuning the system serves + the append-only
    change journal. Read-only (axiom 07): tuning changes only via tuning.toml."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    sections: list[ThresholdSectionView]
    history: list[ThresholdChange]


class MeResult(BaseModel):
    """Identity + saved profile for the wizard's prefill / edit-later."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    user_id: str
    onboarded: bool
    timezone: str | None = None
    email: str | None = None
    profile: UserProfile | None = None
    inbound_calendar_sync_enabled: bool = False


class ReflectionHistoryEntry(BaseModel):
    """One persisted reflection, replayed for display (D2).

    A read copy of a ``ProseAttachmentRecord`` — display only; nothing routes
    on it. The history exists so the coaching notes read as a continuing
    conversation on the Accountability screen, the same continuity the
    reflection prompt now gets."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    created_at: datetime
    summary: str
    detail: list[str] = Field(default_factory=list)
    plan_version: str | None = None


class AccountabilityResult(BaseModel):
    """The read-only accountability projection. Empty-state until a motivation
    profile exists (axiom 21): ``has_motivation_profile`` is False and the
    snapshot fields are ``None`` for a user who skipped that capture."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    has_motivation_profile: bool
    checkin_status: str | None = None
    state: AccountabilityState | None = None
    decision: InterventionDecision | None = None
    checkin_due: bool = False
    """The weekly check-in is due or missed — the SPA renders the "How did
    this week go?" card from this flag."""
    open_recommitment_request_id: str | None = None
    """The latest unanswered recommitment ask for this user, if any — the SPA
    renders the interactive recommitment card from it. A system that asks and
    cannot receive the answer reads as broken (UX pass B3)."""
    reflection_history: list[ReflectionHistoryEntry] = Field(default_factory=list)
    """The user's persisted reflections, newest first (D2) — independent of
    the snapshot fields, so history survives an empty accountability state."""


class RecommitResult(BaseModel):
    """Outcome of answering a recommitment ask. ``replan_required`` is True
    when the typed choice mapped to a recovery mode and parked (or resolved)
    a replan — the draft still flows through review + approval."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    user_id: str
    recommitment_request_id: str
    recommitment_event_id: str
    choice: RecommitmentChoice
    recovery_mode: RecoveryAction | None = None
    replan_required: bool = False
    state: SupervisorState | None = None


class WeeklyCheckinResult(BaseModel):
    """Outcome of submitting the weekly check-in ("How did this week go?").
    Counts are computed server-side from the active draft + telemetry — the
    client supplies only optional blockers prose and an optional recovery
    preference, never the numbers."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    user_id: str
    checkin_id: str
    checkin_status: str
    week_start: date
    week_end: date
    scheduled_task_count: int
    completed_task_count: int
