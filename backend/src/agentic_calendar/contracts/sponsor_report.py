"""``sponsor_report`` contract.

Canonical spec: ``docs/specs/sponsor-report.schema.md``.

A :class:`SponsorReport` is the deterministic, privacy-filtered payload sent to a
trusted third party. It is produced by the Phase 3 Sponsor Report Generator only
when reporting is enabled and permitted, and it passes through the deterministic
privacy filter (``accountability/privacy_filter.py``) before any LLM wording.

The completion numbers come from a :class:`SponsorReportInput` progress snapshot
supplied by the caller. Phase 3 owns the schema, the filter, and the gates; the
telemetry that computes the snapshot (Phase 4) and the policy engine that decides
when to trigger a report (Phase 7) are out of scope here.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .common_types import AccountabilityStatus
from .motivation_profile import SponsorVisibility
from .reason_codes import ReasonCode


class CompletionSummary(BaseModel):
    """Session-level completion counts (spec ``completion_summary``)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    completed_sessions: int = Field(ge=0)
    planned_sessions: int = Field(ge=0)
    on_track_percent: int = Field(ge=0, le=100)

    @model_validator(mode="after")
    def _completed_not_over_planned(self) -> CompletionSummary:
        if self.completed_sessions > self.planned_sessions:
            raise ValueError("completed_sessions must not exceed planned_sessions")
        return self


class MilestoneStatus(BaseModel):
    """One milestone's deterministic status (spec ``milestone_summary[*]``)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    milestone: str = Field(min_length=1)
    status: AccountabilityStatus


class TaskCompletionSummary(BaseModel):
    """Task-level counts (only at ``task_completion`` visibility).

    Counts only — never task titles or descriptions (spec privacy denylist).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    completed_tasks: int = Field(ge=0)
    total_tasks: int = Field(ge=0)

    @model_validator(mode="after")
    def _completed_not_over_total(self) -> TaskCompletionSummary:
        if self.completed_tasks > self.total_tasks:
            raise ValueError("completed_tasks must not exceed total_tasks")
        return self


class SponsorReportInput(BaseModel):
    """Deterministic progress snapshot consumed by the Sponsor Report Generator.

    This is the Phase 3 boundary object: it carries the *already-computed*
    progress numbers. It may carry more detail than a given visibility level
    permits (e.g. ``task_completion_summary`` while the user is at
    ``summary_only``); the generator deterministically strips over-level fields
    via the privacy filter. ``candidate_suggested_support_action`` is the only
    field an LLM may later rephrase, and it is privacy-scanned before send.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    user_id: str = Field(min_length=1)
    plan_id: str = Field(min_length=1)
    status: AccountabilityStatus
    completion_summary: CompletionSummary
    milestone_summary: list[MilestoneStatus] = Field(default_factory=list)
    task_completion_summary: TaskCompletionSummary | None = None
    candidate_suggested_support_action: str | None = None
    next_checkpoint_date: date | None = None


class SponsorReport(BaseModel):
    """Privacy-filtered progress payload for a sponsor.

    Construction does not itself enforce the privacy denylist — that is the
    privacy filter's job, run on the candidate payload before this model is
    built. The model enforces the *structural* visibility invariant
    (``task_completion_summary`` only at ``task_completion``) and numeric
    ranges; ``extra="forbid"`` guarantees no unknown field can ride along.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    report_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    sponsor_id: str = Field(min_length=1)
    plan_id: str = Field(min_length=1)
    visibility_level: SponsorVisibility
    status: AccountabilityStatus
    completion_summary: CompletionSummary
    milestone_summary: list[MilestoneStatus] = Field(default_factory=list)
    task_completion_summary: TaskCompletionSummary | None = None
    suggested_support_action: str | None = None
    next_checkpoint_date: date | None = None
    trigger_reason_code: ReasonCode
    generated_at: datetime
    requires_user_approval_before_send: bool = True

    @model_validator(mode="after")
    def _visibility_not_none(self) -> SponsorReport:
        if self.visibility_level is SponsorVisibility.NONE:
            raise ValueError("a sponsor report must not be built at visibility_level 'none'")
        return self

    @model_validator(mode="after")
    def _task_detail_requires_task_level(self) -> SponsorReport:
        if (
            self.task_completion_summary is not None
            and self.visibility_level is not SponsorVisibility.TASK_COMPLETION
        ):
            raise ValueError(
                "task_completion_summary is only permitted at visibility_level 'task_completion'"
            )
        return self

    @model_validator(mode="after")
    def _generated_at_aware(self) -> SponsorReport:
        if self.generated_at.tzinfo is None:
            raise ValueError("generated_at must be timezone-aware")
        return self


_SHA256_PATTERN = r"^sha256:[0-9a-f]{64}$"


class SponsorReportApproval(BaseModel):
    """Explicit user authorization to send one sponsor report draft.

    The approval records the report's canonical content hash
    (:func:`canonical_sponsor_report_hash`) so the Delivery Service can prove the
    content the user approved equals the content delivered. Approvals are
    immutable once created.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    approval_event_id: str = Field(min_length=1)
    report_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    sponsor_id: str = Field(min_length=1)
    approved_payload_hash: str = Field(pattern=_SHA256_PATTERN)
    created_at: datetime

    @model_validator(mode="after")
    def _created_at_aware(self) -> SponsorReportApproval:
        if self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        return self


def sponsor_report_content_body(report: SponsorReport) -> dict[str, Any]:
    """Serialize the sponsor-visible content of ``report`` — single source of
    truth shared by :func:`canonical_sponsor_report_hash` and the Delivery
    Service's send-time privacy re-scan, so the field set covered by the
    approval hash and the field set re-scanned at send time can never drift
    apart. Volatile metadata (``generated_at``, ``trigger_reason_code``,
    ``requires_user_approval_before_send``) is excluded."""
    return {
        "status": report.status.value,
        "completion_summary": {
            "completed_sessions": report.completion_summary.completed_sessions,
            "planned_sessions": report.completion_summary.planned_sessions,
            "on_track_percent": report.completion_summary.on_track_percent,
        },
        "milestone_summary": [
            {"milestone": m.milestone, "status": m.status.value} for m in report.milestone_summary
        ],
        "task_completion_summary": (
            None
            if report.task_completion_summary is None
            else {
                "completed_tasks": report.task_completion_summary.completed_tasks,
                "total_tasks": report.task_completion_summary.total_tasks,
            }
        ),
        "suggested_support_action": report.suggested_support_action,
        "next_checkpoint_date": (
            None if report.next_checkpoint_date is None else report.next_checkpoint_date.isoformat()
        ),
    }


def canonical_sponsor_report_hash(report: SponsorReport) -> str:
    """Return ``"sha256:<64-hex>"`` over the approved content of ``report``.

    Covers exactly the visibility-filtered body the sponsor would see plus the
    routing identifiers, so the content a user approves is byte-for-byte the
    content delivered. Volatile metadata (``generated_at``,
    ``trigger_reason_code``, ``requires_user_approval_before_send``) is excluded
    so two drafts with identical sponsor-visible content hash equal.

    The Delivery Service recomputes this and compares it to the approval's
    recorded hash; a mismatch means the draft changed after approval and blocks
    delivery (sponsor-report spec "Approved Payload Hash").
    """
    body = {
        "report_id": report.report_id,
        "user_id": report.user_id,
        "sponsor_id": report.sponsor_id,
        "plan_id": report.plan_id,
        "visibility_level": report.visibility_level.value,
        **sponsor_report_content_body(report),
    }
    payload = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"
