"""Tests for the Sponsor Report Generator (Phase 3)."""

from __future__ import annotations

import pytest

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
from agentic_calendar.contracts.sponsor import SponsorStatus
from agentic_calendar.contracts.sponsor_report import MilestoneStatus

from ._builders import T0, build_input, build_profile, build_sponsor


def _gen() -> tuple[SponsorReportGenerator, InMemoryNotificationLogStore]:
    logs = InMemoryNotificationLogStore()
    gen = SponsorReportGenerator(
        clock=FrozenClock(T0),
        id_generator=DeterministicIdGenerator(),
        log_store=logs,
    )
    return gen, logs


def test_generates_draft_when_permitted() -> None:
    gen, logs = _gen()
    out = gen.generate(sponsor=build_sponsor(), profile=build_profile(), progress=build_input())
    assert out.is_draft
    assert out.report is not None
    assert out.report.trigger_reason_code is ReasonCode.SPONSOR_REPORT_PENDING
    assert out.report.requires_user_approval_before_send is True
    assert out.report.visibility_level is SponsorVisibility.SUMMARY_ONLY
    # A drafted log is recorded with no failure reason.
    assert out.log.status is NotificationStatus.DRAFTED
    assert out.log.reason_code is None
    assert logs.list_for_report(out.report.report_id) == [out.log]


def test_summary_only_strips_task_detail() -> None:
    gen, _ = _gen()
    out = gen.generate(
        sponsor=build_sponsor(),
        profile=build_profile(sponsor_visibility_level=SponsorVisibility.SUMMARY_ONLY),
        progress=build_input(),
    )
    assert out.report is not None
    assert out.report.task_completion_summary is None


def test_task_completion_keeps_task_detail() -> None:
    gen, _ = _gen()
    out = gen.generate(
        sponsor=build_sponsor(),
        profile=build_profile(sponsor_visibility_level=SponsorVisibility.TASK_COMPLETION),
        progress=build_input(),
    )
    assert out.report is not None
    assert out.report.task_completion_summary is not None
    assert out.report.task_completion_summary.completed_tasks == 8


def test_milestone_progress_carries_milestones_without_task_detail() -> None:
    gen, _ = _gen()
    out = gen.generate(
        sponsor=build_sponsor(),
        profile=build_profile(sponsor_visibility_level=SponsorVisibility.MILESTONE_PROGRESS),
        progress=build_input(),
    )
    assert out.report is not None
    assert out.report.visibility_level is SponsorVisibility.MILESTONE_PROGRESS
    # Same shape as summary_only in the MVP: milestones kept, task detail dropped.
    assert out.report.task_completion_summary is None
    assert [m.milestone for m in out.report.milestone_summary] == ["Essay draft"]


def test_blocked_when_sponsor_disabled() -> None:
    gen, _ = _gen()
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
    assert out.log.visibility_level is SponsorVisibility.NONE
    assert out.log.engineering_review is False


def test_blocked_when_sponsor_not_accepted() -> None:
    gen, _ = _gen()
    out = gen.generate(
        sponsor=build_sponsor(status=SponsorStatus.PENDING, accepted_at=None),
        profile=build_profile(),
        progress=build_input(),
    )
    assert not out.is_draft
    assert out.log.reason_code is ReasonCode.SPONSOR_PERMISSION_MISSING


def test_blocked_when_profile_points_at_other_sponsor() -> None:
    gen, _ = _gen()
    out = gen.generate(
        sponsor=build_sponsor(sponsor_id="sponsor_001"),
        profile=build_profile(sponsor_id="sponsor_999"),
        progress=build_input(),
    )
    assert not out.is_draft
    assert out.log.reason_code is ReasonCode.SPONSOR_PERMISSION_MISSING


def test_blocked_on_denylisted_milestone_with_engineering_review() -> None:
    gen, _ = _gen()
    out = gen.generate(
        sponsor=build_sponsor(),
        profile=build_profile(),
        progress=build_input(
            milestone_summary=[
                MilestoneStatus(
                    milestone="Calendar Title: Therapy at 3pm",
                    status=AccountabilityStatus.BEHIND,
                )
            ]
        ),
    )
    assert not out.is_draft
    assert out.log.status is NotificationStatus.BLOCKED
    assert out.log.reason_code is ReasonCode.SPONSOR_VISIBILITY_VIOLATION
    assert out.log.engineering_review is True


def test_user_id_mismatch_blocks() -> None:
    gen, _ = _gen()
    out = gen.generate(
        sponsor=build_sponsor(user_id="user_123"),
        profile=build_profile(user_id="user_123"),
        progress=build_input(user_id="user_999"),
    )
    assert not out.is_draft
    assert out.log.reason_code is ReasonCode.SPONSOR_PERMISSION_MISSING


@pytest.mark.parametrize("level", list(SponsorVisibility))
def test_blocked_log_visibility_is_valid_for_every_level(level: SponsorVisibility) -> None:
    """A blocked-permission log must construct for any profile visibility."""
    gen, _ = _gen()
    enabled = level is not SponsorVisibility.NONE
    out = gen.generate(
        sponsor=build_sponsor(status=SponsorStatus.PENDING, accepted_at=None),
        profile=build_profile(
            sponsor_enabled=enabled,
            sponsor_visibility_level=level,
            sponsor_id="sponsor_001" if enabled else None,
        ),
        progress=build_input(),
    )
    assert not out.is_draft
    assert out.log.reason_code is ReasonCode.SPONSOR_PERMISSION_MISSING


def test_report_fields_mirror_input_and_sponsor() -> None:
    gen, _ = _gen()
    sponsor = build_sponsor(sponsor_id="sponsor_001")
    progress = build_input()
    out = gen.generate(
        sponsor=sponsor,
        profile=build_profile(sponsor_visibility_level=SponsorVisibility.TASK_COMPLETION),
        progress=progress,
    )
    r = out.report
    assert r is not None
    # Identifiers and progress data are copied faithfully from the inputs.
    assert r.user_id == progress.user_id
    assert r.plan_id == progress.plan_id
    assert r.sponsor_id == sponsor.sponsor_id
    assert r.status is progress.status
    assert r.completion_summary == progress.completion_summary
    assert r.milestone_summary == progress.milestone_summary
    assert r.task_completion_summary == progress.task_completion_summary
    assert r.suggested_support_action == progress.candidate_suggested_support_action
    assert r.next_checkpoint_date == progress.next_checkpoint_date


def test_optional_fields_pass_through_as_none() -> None:
    gen, _ = _gen()
    out = gen.generate(
        sponsor=build_sponsor(),
        profile=build_profile(),
        progress=build_input(
            milestone_summary=[],
            task_completion_summary=None,
            candidate_suggested_support_action=None,
            next_checkpoint_date=None,
        ),
    )
    r = out.report
    assert r is not None
    assert r.milestone_summary == []
    assert r.task_completion_summary is None
    assert r.suggested_support_action is None
    assert r.next_checkpoint_date is None


def test_generated_at_and_report_id_are_deterministic() -> None:
    gen, _ = _gen()
    first = gen.generate(sponsor=build_sponsor(), profile=build_profile(), progress=build_input())
    second = gen.generate(sponsor=build_sponsor(), profile=build_profile(), progress=build_input())
    assert first.report is not None and second.report is not None
    # generated_at comes from the injected frozen clock.
    assert first.report.generated_at == T0
    # report ids come from the injected id generator and are unique per call.
    assert first.report.report_id != second.report.report_id
