"""Typed results every cycle operation returns.

These are the operator-facing summaries the CLI serializes. They reuse the
contract models for anything structured (unscheduled tasks, drift events)
so a typed ``reason_code`` is never flattened into prose, and they carry the
LLM prose nodes' output (reflection / explanation) as *attachments* — the
deterministic fields are always sufficient to act on without reading them.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from agentic_calendar.contracts.accountability_intervention import InterventionDecision
from agentic_calendar.contracts.accountability_state import AccountabilityState
from agentic_calendar.contracts.checkin_event import RecoveryAction
from agentic_calendar.contracts.draft_schedule import DraftSchedule
from agentic_calendar.contracts.drift_event import DriftEvent
from agentic_calendar.contracts.reason_codes import ReasonCode
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


class AccountabilityResult(BaseModel):
    """The read-only accountability projection. Empty-state until a motivation
    profile exists (axiom 21): ``has_motivation_profile`` is False and the
    snapshot fields are ``None`` for a user who skipped that capture."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    has_motivation_profile: bool
    checkin_status: str | None = None
    state: AccountabilityState | None = None
    decision: InterventionDecision | None = None
