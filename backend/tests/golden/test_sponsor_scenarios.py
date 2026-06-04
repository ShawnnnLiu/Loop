"""Golden scenarios for Phase 3 sponsor reporting (docs/golden-test-cases.md).

Covers scenarios 17-20 and 25 — the sponsor-reporting slice. These assert the
behavior Phase 3 *owns*: given a deterministic progress snapshot, the generator
produces or blocks a draft, the privacy filter enforces the denylist, a
visibility downgrade strips over-level detail, and delivery re-checks privacy
before send.

Scope note: the *trigger* that decides a report is warranted (e.g. "missed 4
tasks in 7 days") is the Phase 7 Accountability Policy Engine reading Phase 4
telemetry. The scenarios below supply the equivalent progress snapshot directly
and verify the deterministic draft/filter/gate behavior that is Phase 3's
responsibility. Scenario 18's ``ACCOUNTABILITY_CONTRACT_INACTIVE`` framing is the
policy engine's; at the generator level the sponsor path blocks with
``SPONSOR_PERMISSION_MISSING``.
"""

from __future__ import annotations

import pytest

from agentic_calendar.accountability.delivery import SponsorReportDeliveryService
from agentic_calendar.accountability.notification_log_store import (
    InMemoryNotificationLogStore,
)
from agentic_calendar.accountability.report_generator import SponsorReportGenerator
from agentic_calendar.common.clock import FrozenClock
from agentic_calendar.common.ids import DeterministicIdGenerator
from agentic_calendar.contracts.common_types import AccountabilityStatus
from agentic_calendar.contracts.motivation_profile import SponsorVisibility
from agentic_calendar.contracts.notification_log import NotificationStatus
from agentic_calendar.contracts.reason_codes import ReasonCode
from agentic_calendar.contracts.sponsor_report import (
    MilestoneStatus,
    SponsorReportApproval,
    canonical_sponsor_report_hash,
)
from tests.accountability._builders import (
    T0,
    build_input,
    build_profile,
    build_sponsor,
)

pytestmark = pytest.mark.golden


def _generator(
    logs: InMemoryNotificationLogStore | None = None,
) -> tuple[SponsorReportGenerator, InMemoryNotificationLogStore]:
    store = logs or InMemoryNotificationLogStore()
    gen = SponsorReportGenerator(
        clock=FrozenClock(T0),
        id_generator=DeterministicIdGenerator(),
        log_store=store,
    )
    return gen, store


def test_scenario_17_sponsor_summary_when_enabled_and_threshold_hit() -> None:
    gen, _ = _generator()
    out = gen.generate(
        sponsor=build_sponsor(),
        profile=build_profile(
            sponsor_enabled=True,
            sponsor_visibility_level=SponsorVisibility.SUMMARY_ONLY,
        ),
        progress=build_input(),
    )
    assert out.is_draft
    assert out.report is not None
    assert out.report.trigger_reason_code is ReasonCode.SPONSOR_REPORT_PENDING
    assert out.report.visibility_level is SponsorVisibility.SUMMARY_ONLY
    assert out.report.requires_user_approval_before_send is True
    # summary_only never carries task-level detail.
    assert out.report.task_completion_summary is None


def test_scenario_18_sponsor_disabled_no_report_generated() -> None:
    gen, logs = _generator()
    out = gen.generate(
        sponsor=build_sponsor(),
        profile=build_profile(
            sponsor_enabled=False,
            sponsor_visibility_level=SponsorVisibility.NONE,
            sponsor_id=None,
        ),
        progress=build_input(),
    )
    assert not out.is_draft
    assert out.report is None
    assert out.log.status is NotificationStatus.BLOCKED
    assert out.log.reason_code is ReasonCode.SPONSOR_PERMISSION_MISSING
    # No draft persisted beyond the single blocked audit entry.
    assert [log.status for log in logs.list_for_user("user_123")] == [NotificationStatus.BLOCKED]


def test_scenario_19_privacy_filter_blocks_and_logs_engineering_review() -> None:
    gen, logs = _generator()
    out = gen.generate(
        sponsor=build_sponsor(),
        profile=build_profile(),
        progress=build_input(
            milestone_summary=[
                MilestoneStatus(
                    milestone="Calendar Title: Therapy with Dr. Lee",
                    status=AccountabilityStatus.BEHIND,
                )
            ]
        ),
    )
    assert not out.is_draft
    assert out.log.status is NotificationStatus.BLOCKED
    assert out.log.reason_code is ReasonCode.SPONSOR_VISIBILITY_VIOLATION
    # An engineering-review entry is written for the blocked draft.
    assert out.log.engineering_review is True
    assert logs.list_for_report(out.log.report_id) == [out.log]


def test_scenario_20_visibility_downgrade_strips_task_detail() -> None:
    gen, _ = _generator()
    # Before: task_completion visibility includes task-level detail.
    high = gen.generate(
        sponsor=build_sponsor(),
        profile=build_profile(sponsor_visibility_level=SponsorVisibility.TASK_COMPLETION),
        progress=build_input(),
    )
    assert high.report is not None
    assert high.report.task_completion_summary is not None

    # After downgrade: the next generated report carries summary fields only.
    low = gen.generate(
        sponsor=build_sponsor(),
        profile=build_profile(sponsor_visibility_level=SponsorVisibility.SUMMARY_ONLY),
        progress=build_input(),
    )
    assert low.report is not None
    assert low.report.visibility_level is SponsorVisibility.SUMMARY_ONLY
    assert low.report.task_completion_summary is None


def test_scenario_25_disallowed_llm_wording_rejected_before_send() -> None:
    # A clean draft is produced and approved.
    gen, _ = _generator()
    drafted = gen.generate(sponsor=build_sponsor(), profile=build_profile(), progress=build_input())
    assert drafted.report is not None

    # An LLM wording pass then injects disallowed content into the action text.
    leaky = drafted.report.model_copy(
        update={"suggested_support_action": "Diagnosis: severe anxiety this week"}
    )
    approval = SponsorReportApproval(
        approval_event_id="appr_25",
        report_id=leaky.report_id,
        user_id=leaky.user_id,
        sponsor_id=leaky.sponsor_id,
        approved_payload_hash=canonical_sponsor_report_hash(leaky),
        created_at=T0,
    )
    delivery = SponsorReportDeliveryService(
        clock=FrozenClock(T0),
        id_generator=DeterministicIdGenerator(),
        log_store=InMemoryNotificationLogStore(),
    )
    out = delivery.deliver(
        report=leaky,
        sponsor=build_sponsor(),
        profile=build_profile(),
        approval=approval,
    )
    assert out.delivered is False
    assert out.reason_code is ReasonCode.SPONSOR_VISIBILITY_VIOLATION
    assert out.log.engineering_review is True
