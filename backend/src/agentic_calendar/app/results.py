"""Typed results every cycle operation returns.

These are the operator-facing summaries the CLI serializes. They reuse the
contract models for anything structured (unscheduled tasks, drift events)
so a typed ``reason_code`` is never flattened into prose, and they carry the
LLM prose nodes' output (reflection / explanation) as *attachments* — the
deterministic fields are always sufficient to act on without reading them.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from agentic_calendar.contracts.checkin_event import RecoveryAction
from agentic_calendar.contracts.drift_event import DriftEvent
from agentic_calendar.contracts.reason_codes import ReasonCode
from agentic_calendar.contracts.scheduler_output import RepairOption, UnscheduledTask
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
    explanation: UserExplanation | None = None
    """LLM prose attachment (validation wording); never control-plane."""


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
