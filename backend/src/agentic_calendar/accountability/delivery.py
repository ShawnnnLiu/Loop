"""Sponsor Report Delivery Service (Phase 3).

Spec: ``docs/specs/notification-log.schema.md``,
``docs/axioms/21-accountability-layer.md``, ``docs/axioms/06-calendar-safety.md``.

Delivery is the final gate before a sponsor report leaves the system. It
re-enforces every guarantee at send time — permission, privacy, and explicit
user approval — because the draft may have been built earlier and the world (or
the wording) may have changed since. Sending is an external side effect, so the
path supports ``dry_run``; a delivered notification cannot be recalled, so
integrity is enforced *before* send via the approved-payload-hash recheck rather
than by rollback.

Every attempt — sent, dry-run, or blocked — writes a :class:`NotificationLog`.
The MVP records delivery intent and outcome; the concrete channel transport
(email/push/in-app) is wired in a later phase.
"""

from __future__ import annotations

from dataclasses import dataclass

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
    SponsorReportApproval,
    canonical_sponsor_report_hash,
    sponsor_report_content_body,
)

from .notification_log_store import NotificationLogStore
from .privacy_filter import PrivacyFilter


@dataclass(frozen=True)
class DeliveryOutcome:
    """Result of a delivery attempt.

    ``delivered`` is true only when a report was actually sent (never on a
    dry-run or a block). ``log`` is always the persisted audit record.
    """

    delivered: bool
    log: NotificationLog

    @property
    def reason_code(self) -> ReasonCode | None:
        return self.log.reason_code


class SponsorReportDeliveryService:
    """Send an approved sponsor report, re-enforcing all gates at send time."""

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

    def deliver(
        self,
        *,
        report: SponsorReport,
        sponsor: Sponsor,
        profile: MotivationProfile,
        approval: SponsorReportApproval | None = None,
        dry_run: bool = False,
    ) -> DeliveryOutcome:
        if not self._permission_holds(report, sponsor, profile):
            return self._blocked(
                report,
                sponsor,
                ReasonCode.SPONSOR_PERMISSION_MISSING,
                engineering_review=False,
            )

        verdict = self._filter.scan(self._report_body_for_scan(report), report.visibility_level)
        if not verdict.ok:
            return self._blocked(
                report,
                sponsor,
                ReasonCode.SPONSOR_VISIBILITY_VIOLATION,
                engineering_review=True,
            )

        # Phase 3 generators always set ``requires_user_approval_before_send``
        # True, so the gate below always runs. A False flag would mean
        # "pre-approved by contract" (axiom 21 line 168) — that path is deferred
        # to Phase 7 and no Phase 3 producer emits it.
        if report.requires_user_approval_before_send and not self._approval_valid(report, approval):
            return self._blocked(
                report,
                sponsor,
                ReasonCode.USER_APPROVAL_REQUIRED,
                engineering_review=False,
            )

        status = NotificationStatus.DRY_RUN if dry_run else NotificationStatus.SENT
        log = self._log(report, sponsor, status, reason_code=None, dry_run=dry_run)
        return DeliveryOutcome(delivered=not dry_run, log=log)

    def record_approval(
        self,
        *,
        report: SponsorReport,
        sponsor: Sponsor,
        profile: MotivationProfile,
        approval: SponsorReportApproval,
    ) -> DeliveryOutcome:
        """Record the user's explicit approval of a draft as an audit entry.

        Axiom 21 requires generation, approval, and delivery to each be logged;
        this writes the ``approved`` entry that sits between the generator's
        ``drafted`` entry and ``deliver``'s ``sent`` entry. It re-runs the same
        permission, privacy, and approval-validity gates as ``deliver`` so an
        approval can never be logged for a report that could not be sent.
        ``delivered`` is always ``False`` here — approval is not delivery.
        """
        if not self._permission_holds(report, sponsor, profile):
            return self._blocked(
                report,
                sponsor,
                ReasonCode.SPONSOR_PERMISSION_MISSING,
                engineering_review=False,
            )
        if not self._filter.scan(self._report_body_for_scan(report), report.visibility_level).ok:
            return self._blocked(
                report,
                sponsor,
                ReasonCode.SPONSOR_VISIBILITY_VIOLATION,
                engineering_review=True,
            )
        if not self._approval_valid(report, approval):
            return self._blocked(
                report,
                sponsor,
                ReasonCode.USER_APPROVAL_REQUIRED,
                engineering_review=False,
            )
        log = self._log(
            report,
            sponsor,
            NotificationStatus.APPROVED,
            reason_code=None,
            dry_run=False,
        )
        return DeliveryOutcome(delivered=False, log=log)

    def _permission_holds(
        self, report: SponsorReport, sponsor: Sponsor, profile: MotivationProfile
    ) -> bool:
        return (
            profile.sponsor_enabled
            and profile.sponsor_visibility_level is not SponsorVisibility.NONE
            and profile.sponsor_id == sponsor.sponsor_id == report.sponsor_id
            and sponsor.is_reportable()
            and profile.user_id == sponsor.user_id == report.user_id
        )

    def _approval_valid(
        self, report: SponsorReport, approval: SponsorReportApproval | None
    ) -> bool:
        """True iff ``approval`` authorizes exactly this report's content.

        The hash recheck guarantees the approved draft equals the draft being
        sent; if the report was edited after approval (or the wording changed),
        the hash diverges and the user must re-approve.
        """
        if approval is None:
            return False
        if approval.report_id != report.report_id:
            return False
        if approval.sponsor_id != report.sponsor_id:
            return False
        if approval.user_id != report.user_id:
            return False
        return approval.approved_payload_hash == canonical_sponsor_report_hash(report)

    def _report_body_for_scan(self, report: SponsorReport) -> dict[str, object]:
        # Delegates to the contract's shared serializer so the send-time
        # re-scan covers exactly the field set the approval hash covers —
        # the two can never silently drift apart.
        return sponsor_report_content_body(report)

    def _blocked(
        self,
        report: SponsorReport,
        sponsor: Sponsor,
        reason_code: ReasonCode,
        *,
        engineering_review: bool,
    ) -> DeliveryOutcome:
        log = self._log(
            report,
            sponsor,
            NotificationStatus.BLOCKED,
            reason_code=reason_code,
            dry_run=False,
            engineering_review=engineering_review,
        )
        return DeliveryOutcome(delivered=False, log=log)

    def _log(
        self,
        report: SponsorReport,
        sponsor: Sponsor,
        status: NotificationStatus,
        *,
        reason_code: ReasonCode | None,
        dry_run: bool,
        engineering_review: bool = False,
    ) -> NotificationLog:
        log = NotificationLog(
            notification_log_id=self._ids.new_id("notif"),
            report_id=report.report_id,
            sponsor_id=sponsor.sponsor_id,
            user_id=report.user_id,
            visibility_level=report.visibility_level,
            channel=sponsor.contact_channel,
            status=status,
            reason_code=reason_code,
            engineering_review=engineering_review,
            dry_run=dry_run,
            created_at=self._clock.now(),
        )
        self._logs.append(log)
        return log
