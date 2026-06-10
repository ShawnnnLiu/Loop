"""Tests for the Sponsor Report Delivery Service (Phase 3)."""

from __future__ import annotations

from agentic_calendar.accountability.delivery import SponsorReportDeliveryService
from agentic_calendar.accountability.notification_log_store import (
    InMemoryNotificationLogStore,
)
from agentic_calendar.accountability.report_generator import SponsorReportGenerator
from agentic_calendar.common.clock import FrozenClock
from agentic_calendar.common.ids import DeterministicIdGenerator
from agentic_calendar.contracts.common_types import AccountabilityStatus
from agentic_calendar.contracts.notification_log import NotificationStatus
from agentic_calendar.contracts.reason_codes import ReasonCode
from agentic_calendar.contracts.sponsor import SponsorStatus
from agentic_calendar.contracts.sponsor_report import (
    MilestoneStatus,
    SponsorReport,
    SponsorReportApproval,
    canonical_sponsor_report_hash,
    sponsor_report_content_body,
)

from ._builders import T0, build_input, build_profile, build_sponsor


def _drafted_report() -> SponsorReport:
    logs = InMemoryNotificationLogStore()
    gen = SponsorReportGenerator(
        clock=FrozenClock(T0),
        id_generator=DeterministicIdGenerator(),
        log_store=logs,
    )
    out = gen.generate(sponsor=build_sponsor(), profile=build_profile(), progress=build_input())
    assert out.report is not None
    return out.report


def _service() -> tuple[SponsorReportDeliveryService, InMemoryNotificationLogStore]:
    logs = InMemoryNotificationLogStore()
    svc = SponsorReportDeliveryService(
        clock=FrozenClock(T0),
        id_generator=DeterministicIdGenerator(),
        log_store=logs,
    )
    return svc, logs


def _approval_for(report: SponsorReport) -> SponsorReportApproval:
    return SponsorReportApproval(
        approval_event_id="appr_1",
        report_id=report.report_id,
        user_id=report.user_id,
        sponsor_id=report.sponsor_id,
        approved_payload_hash=canonical_sponsor_report_hash(report),
        created_at=T0,
    )


def test_blocked_without_approval() -> None:
    svc, logs = _service()
    report = _drafted_report()
    out = svc.deliver(report=report, sponsor=build_sponsor(), profile=build_profile())
    assert out.delivered is False
    assert out.log.status is NotificationStatus.BLOCKED
    assert out.reason_code is ReasonCode.USER_APPROVAL_REQUIRED
    assert logs.list_for_report(report.report_id) == [out.log]


def test_delivers_with_valid_approval() -> None:
    svc, _ = _service()
    report = _drafted_report()
    out = svc.deliver(
        report=report,
        sponsor=build_sponsor(),
        profile=build_profile(),
        approval=_approval_for(report),
    )
    assert out.delivered is True
    assert out.log.status is NotificationStatus.SENT
    assert out.log.reason_code is None


def test_dry_run_does_not_deliver() -> None:
    svc, _ = _service()
    report = _drafted_report()
    out = svc.deliver(
        report=report,
        sponsor=build_sponsor(),
        profile=build_profile(),
        approval=_approval_for(report),
        dry_run=True,
    )
    assert out.delivered is False
    assert out.log.status is NotificationStatus.DRY_RUN
    assert out.log.dry_run is True


def test_stale_approval_hash_blocks() -> None:
    svc, _ = _service()
    report = _drafted_report()
    approval = _approval_for(report)
    # The draft changed after approval (wording edited) -> hash diverges.
    edited = report.model_copy(update={"suggested_support_action": "Different text"})
    out = svc.deliver(
        report=edited,
        sponsor=build_sponsor(),
        profile=build_profile(),
        approval=approval,
    )
    assert out.delivered is False
    assert out.reason_code is ReasonCode.USER_APPROVAL_REQUIRED


def test_approval_for_other_report_blocks() -> None:
    svc, _ = _service()
    report = _drafted_report()
    foreign = SponsorReportApproval(
        approval_event_id="appr_2",
        report_id="some_other_report",
        user_id=report.user_id,
        sponsor_id=report.sponsor_id,
        approved_payload_hash=canonical_sponsor_report_hash(report),
        created_at=T0,
    )
    out = svc.deliver(
        report=report,
        sponsor=build_sponsor(),
        profile=build_profile(),
        approval=foreign,
    )
    assert out.delivered is False
    assert out.reason_code is ReasonCode.USER_APPROVAL_REQUIRED


def test_revoked_sponsor_blocks_delivery() -> None:
    svc, _ = _service()
    report = _drafted_report()
    out = svc.deliver(
        report=report,
        sponsor=build_sponsor(status=SponsorStatus.REVOKED, accepted_at=None, revoked_at=T0),
        profile=build_profile(),
        approval=_approval_for(report),
    )
    assert out.delivered is False
    assert out.reason_code is ReasonCode.SPONSOR_PERMISSION_MISSING


def test_send_safety_privacy_recheck_blocks_leaky_wording() -> None:
    """Scenario 25: LLM-rephrased action leaks private content -> blocked."""
    svc, _ = _service()
    report = _drafted_report()
    leaky = report.model_copy(update={"suggested_support_action": "Diagnosis: anxiety; relax"})
    approval = SponsorReportApproval(
        approval_event_id="appr_3",
        report_id=leaky.report_id,
        user_id=leaky.user_id,
        sponsor_id=leaky.sponsor_id,
        approved_payload_hash=canonical_sponsor_report_hash(leaky),
        created_at=T0,
    )
    out = svc.deliver(
        report=leaky,
        sponsor=build_sponsor(),
        profile=build_profile(),
        approval=approval,
    )
    assert out.delivered is False
    assert out.reason_code is ReasonCode.SPONSOR_VISIBILITY_VIOLATION
    assert out.log.engineering_review is True


def test_send_safety_privacy_recheck_blocks_leaky_milestone() -> None:
    """The send-time re-scan must catch denylisted content in milestone
    wording, not just in ``suggested_support_action``."""
    svc, _ = _service()
    report = _drafted_report()
    leaky = report.model_copy(
        update={
            "milestone_summary": [
                MilestoneStatus(
                    milestone="Diagnosis: anxiety around essay draft",
                    status=AccountabilityStatus.BEHIND,
                )
            ]
        }
    )
    approval = SponsorReportApproval(
        approval_event_id="appr_4",
        report_id=leaky.report_id,
        user_id=leaky.user_id,
        sponsor_id=leaky.sponsor_id,
        approved_payload_hash=canonical_sponsor_report_hash(leaky),
        created_at=T0,
    )
    out = svc.deliver(
        report=leaky,
        sponsor=build_sponsor(),
        profile=build_profile(),
        approval=approval,
    )
    assert out.delivered is False
    assert out.reason_code is ReasonCode.SPONSOR_VISIBILITY_VIOLATION
    assert out.log.engineering_review is True


def test_delivery_scan_field_set_matches_generator_scan_body() -> None:
    """Parity guard: the send-time re-scan (shared with the approval hash via
    ``sponsor_report_content_body``) must cover exactly the content fields the
    generator scanned at draft time, so a field added to the report model can
    never be scanned at one stage and skipped at the other."""
    content_keys = set(sponsor_report_content_body(_drafted_report()))
    gen = SponsorReportGenerator(
        clock=FrozenClock(T0),
        id_generator=DeterministicIdGenerator(),
        log_store=InMemoryNotificationLogStore(),
    )
    candidate_keys = set(gen._candidate_body(build_input(), include_task=True))
    assert content_keys == candidate_keys


def test_record_approval_writes_approved_log() -> None:
    svc, logs = _service()
    report = _drafted_report()
    out = svc.record_approval(
        report=report,
        sponsor=build_sponsor(),
        profile=build_profile(),
        approval=_approval_for(report),
    )
    # Approval is logged but is not itself a delivery.
    assert out.delivered is False
    assert out.log.status is NotificationStatus.APPROVED
    assert out.log.reason_code is None
    assert logs.list_for_report(report.report_id) == [out.log]


def test_record_approval_blocks_stale_approval() -> None:
    svc, _ = _service()
    report = _drafted_report()
    approval = _approval_for(report)
    edited = report.model_copy(update={"suggested_support_action": "changed wording"})
    out = svc.record_approval(
        report=edited,
        sponsor=build_sponsor(),
        profile=build_profile(),
        approval=approval,
    )
    assert out.log.status is NotificationStatus.BLOCKED
    assert out.reason_code is ReasonCode.USER_APPROVAL_REQUIRED


def test_record_approval_blocks_revoked_sponsor() -> None:
    svc, _ = _service()
    report = _drafted_report()
    out = svc.record_approval(
        report=report,
        sponsor=build_sponsor(status=SponsorStatus.REVOKED, accepted_at=None, revoked_at=T0),
        profile=build_profile(),
        approval=_approval_for(report),
    )
    assert out.log.status is NotificationStatus.BLOCKED
    assert out.reason_code is ReasonCode.SPONSOR_PERMISSION_MISSING


def test_approval_for_other_sponsor_blocks() -> None:
    svc, _ = _service()
    report = _drafted_report()
    # report_id matches but the approval names a different sponsor.
    approval = SponsorReportApproval(
        approval_event_id="appr_sp",
        report_id=report.report_id,
        user_id=report.user_id,
        sponsor_id="some_other_sponsor",
        approved_payload_hash=canonical_sponsor_report_hash(report),
        created_at=T0,
    )
    out = svc.deliver(
        report=report,
        sponsor=build_sponsor(),
        profile=build_profile(),
        approval=approval,
    )
    assert out.delivered is False
    assert out.reason_code is ReasonCode.USER_APPROVAL_REQUIRED


def test_approval_for_other_user_blocks() -> None:
    svc, _ = _service()
    report = _drafted_report()
    approval = SponsorReportApproval(
        approval_event_id="appr_usr",
        report_id=report.report_id,
        user_id="some_other_user",
        sponsor_id=report.sponsor_id,
        approved_payload_hash=canonical_sponsor_report_hash(report),
        created_at=T0,
    )
    out = svc.deliver(
        report=report,
        sponsor=build_sponsor(),
        profile=build_profile(),
        approval=approval,
    )
    assert out.delivered is False
    assert out.reason_code is ReasonCode.USER_APPROVAL_REQUIRED


def test_record_approval_blocks_denylisted_report() -> None:
    svc, _ = _service()
    report = _drafted_report()
    leaky = report.model_copy(
        update={"suggested_support_action": "Private note: do not share this"}
    )
    approval = SponsorReportApproval(
        approval_event_id="appr_leak",
        report_id=leaky.report_id,
        user_id=leaky.user_id,
        sponsor_id=leaky.sponsor_id,
        approved_payload_hash=canonical_sponsor_report_hash(leaky),
        created_at=T0,
    )
    out = svc.record_approval(
        report=leaky,
        sponsor=build_sponsor(),
        profile=build_profile(),
        approval=approval,
    )
    assert out.log.status is NotificationStatus.BLOCKED
    assert out.reason_code is ReasonCode.SPONSOR_VISIBILITY_VIOLATION
    assert out.log.engineering_review is True


def test_sent_log_records_required_audit_fields() -> None:
    svc, _ = _service()
    report = _drafted_report()
    sponsor = build_sponsor()
    out = svc.deliver(
        report=report,
        sponsor=sponsor,
        profile=build_profile(),
        approval=_approval_for(report),
    )
    log = out.log
    # Phase 3 acceptance: every delivery logs report_id, sponsor_id,
    # visibility_level, and status.
    assert log.report_id == report.report_id
    assert log.sponsor_id == sponsor.sponsor_id
    assert log.user_id == report.user_id
    assert log.visibility_level is report.visibility_level
    assert log.channel is sponsor.contact_channel
    assert log.status is NotificationStatus.SENT
    assert log.reason_code is None
    assert log.dry_run is False
    assert log.engineering_review is False


def test_each_attempt_is_logged_in_order() -> None:
    svc, logs = _service()
    report = _drafted_report()
    sponsor = build_sponsor()
    profile = build_profile()
    # Attempt 1: no approval -> blocked. Attempt 2: approved. Attempt 3: sent.
    svc.deliver(report=report, sponsor=sponsor, profile=profile)
    svc.record_approval(
        report=report, sponsor=sponsor, profile=profile, approval=_approval_for(report)
    )
    svc.deliver(report=report, sponsor=sponsor, profile=profile, approval=_approval_for(report))
    statuses = [log.status for log in logs.list_for_report(report.report_id)]
    assert statuses == [
        NotificationStatus.BLOCKED,
        NotificationStatus.APPROVED,
        NotificationStatus.SENT,
    ]
