"""Sponsor Report Generator (Phase 3).

Spec: ``docs/specs/sponsor-report.schema.md``,
``docs/axioms/21-accountability-layer.md``.

Given a deterministic progress snapshot (:class:`SponsorReportInput`), the user's
:class:`MotivationProfile`, and the :class:`Sponsor` row, the generator either
produces a privacy-filtered :class:`SponsorReport` *draft* (awaiting user
approval) or blocks with a typed reason code. Every outcome writes a
:class:`NotificationLog`.

Determinism: permission, visibility level, included fields, and the trigger
reason code are all chosen by this code. The only LLM-touchable field is
``suggested_support_action`` wording, which is privacy-scanned before it can be
sent. The LLM never selects fields or status (axiom 21 "Hard Rules").
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agentic_calendar.common.clock import Clock
from agentic_calendar.common.ids import IdGenerator
from agentic_calendar.contracts.motivation_profile import (
    MotivationProfile,
    SponsorVisibility,
)
from agentic_calendar.contracts.notification_log import (
    NotificationLog,
    NotificationStatus,
)
from agentic_calendar.contracts.reason_codes import ReasonCode
from agentic_calendar.contracts.sponsor import Sponsor
from agentic_calendar.contracts.sponsor_report import (
    SponsorReport,
    SponsorReportInput,
)

from .notification_log_store import NotificationLogStore
from .privacy_filter import PrivacyFilter


@dataclass(frozen=True)
class GenerationOutcome:
    """Result of a generation attempt.

    ``report`` is the draft when generation succeeded, else ``None``. ``log`` is
    always the persisted audit record for the attempt.
    """

    report: SponsorReport | None
    log: NotificationLog

    @property
    def is_draft(self) -> bool:
        return self.report is not None


class SponsorReportGenerator:
    """Deterministically build a privacy-filtered sponsor report draft."""

    def __init__(
        self,
        *,
        clock: Clock,
        id_generator: IdGenerator,
        log_store: NotificationLogStore,
        privacy_filter: PrivacyFilter | None = None,
    ) -> None:
        self._clock = clock
        self._ids = id_generator
        self._logs = log_store
        self._filter = privacy_filter or PrivacyFilter()

    def generate(
        self,
        *,
        sponsor: Sponsor,
        profile: MotivationProfile,
        progress: SponsorReportInput,
    ) -> GenerationOutcome:
        report_id = self._ids.new_id("report")
        visibility = profile.sponsor_visibility_level

        permission_error = self._permission_error(sponsor, profile, progress)
        if permission_error is not None:
            return self._blocked(
                report_id=report_id,
                sponsor=sponsor,
                user_id=progress.user_id,
                visibility=visibility,
                reason_code=permission_error,
                engineering_review=False,
            )

        # Permission holds, so visibility is non-`none` here.
        include_task = visibility is SponsorVisibility.TASK_COMPLETION
        candidate = self._candidate_body(progress, include_task=include_task)

        verdict = self._filter.scan(candidate, visibility)
        if not verdict.ok:
            return self._blocked(
                report_id=report_id,
                sponsor=sponsor,
                user_id=progress.user_id,
                visibility=visibility,
                reason_code=ReasonCode.SPONSOR_VISIBILITY_VIOLATION,
                engineering_review=True,
            )

        report = SponsorReport(
            report_id=report_id,
            user_id=progress.user_id,
            sponsor_id=sponsor.sponsor_id,
            plan_id=progress.plan_id,
            visibility_level=visibility,
            status=progress.status,
            completion_summary=progress.completion_summary,
            milestone_summary=list(progress.milestone_summary),
            task_completion_summary=(progress.task_completion_summary if include_task else None),
            suggested_support_action=progress.candidate_suggested_support_action,
            next_checkpoint_date=progress.next_checkpoint_date,
            trigger_reason_code=ReasonCode.SPONSOR_REPORT_PENDING,
            generated_at=self._clock.now(),
            # Phase 3 always gates on explicit user approval; a contract-based
            # pre-approval path is deferred (axiom 21 line 168).
            requires_user_approval_before_send=True,
        )

        log = NotificationLog(
            notification_log_id=self._ids.new_id("notif"),
            report_id=report_id,
            sponsor_id=sponsor.sponsor_id,
            user_id=progress.user_id,
            visibility_level=visibility,
            channel=sponsor.contact_channel,
            status=NotificationStatus.DRAFTED,
            reason_code=None,
            engineering_review=False,
            dry_run=False,
            created_at=self._clock.now(),
        )
        self._logs.append(log)
        return GenerationOutcome(report=report, log=log)

    def _permission_error(
        self,
        sponsor: Sponsor,
        profile: MotivationProfile,
        progress: SponsorReportInput,
    ) -> ReasonCode | None:
        """Return a reason code if reporting is not permitted, else ``None``.

        All four conditions must hold (axiom 21 "Sponsor Report Rules"): the
        profile enables reporting, names a non-`none` visibility, points at this
        sponsor, and the sponsor row is ``accepted``. User-id consistency across
        the three objects is required so a report can never be built for the
        wrong subject.
        """
        if not profile.sponsor_enabled:
            return ReasonCode.SPONSOR_PERMISSION_MISSING
        # Defense-in-depth guard. Structurally unreachable today: the
        # MotivationProfile invariant forbids ``sponsor_enabled`` with a ``none``
        # visibility, so the check above already returned. Kept explicit so the
        # permission predicate still holds if that invariant is ever loosened.
        if profile.sponsor_visibility_level is SponsorVisibility.NONE:
            return ReasonCode.SPONSOR_PERMISSION_MISSING
        if profile.sponsor_id != sponsor.sponsor_id:
            return ReasonCode.SPONSOR_PERMISSION_MISSING
        if not sponsor.is_reportable():
            return ReasonCode.SPONSOR_PERMISSION_MISSING
        if not (profile.user_id == sponsor.user_id == progress.user_id):
            return ReasonCode.SPONSOR_PERMISSION_MISSING
        return None

    def _candidate_body(
        self, progress: SponsorReportInput, *, include_task: bool
    ) -> dict[str, Any]:
        """Assemble the scan dict mirroring the report body to be built."""
        return {
            "status": progress.status.value,
            "completion_summary": {
                "completed_sessions": progress.completion_summary.completed_sessions,
                "planned_sessions": progress.completion_summary.planned_sessions,
                "on_track_percent": progress.completion_summary.on_track_percent,
            },
            "milestone_summary": [
                {"milestone": m.milestone, "status": m.status.value}
                for m in progress.milestone_summary
            ],
            "task_completion_summary": (
                None
                if (progress.task_completion_summary is None or not include_task)
                else {
                    "completed_tasks": progress.task_completion_summary.completed_tasks,
                    "total_tasks": progress.task_completion_summary.total_tasks,
                }
            ),
            "suggested_support_action": progress.candidate_suggested_support_action,
            "next_checkpoint_date": (
                None
                if progress.next_checkpoint_date is None
                else progress.next_checkpoint_date.isoformat()
            ),
        }

    def _blocked(
        self,
        *,
        report_id: str,
        sponsor: Sponsor,
        user_id: str,
        visibility: SponsorVisibility,
        reason_code: ReasonCode,
        engineering_review: bool,
    ) -> GenerationOutcome:
        log = NotificationLog(
            notification_log_id=self._ids.new_id("notif"),
            report_id=report_id,
            sponsor_id=sponsor.sponsor_id,
            user_id=user_id,
            visibility_level=visibility,
            channel=sponsor.contact_channel,
            status=NotificationStatus.BLOCKED,
            reason_code=reason_code,
            engineering_review=engineering_review,
            dry_run=False,
            created_at=self._clock.now(),
        )
        self._logs.append(log)
        return GenerationOutcome(report=None, log=log)
