"""Tiny deterministic builders for accountability-region tests.

Kept under ``tests/`` (not ``src/``) as test-only infrastructure. Each builder
returns a fully valid object with sensible defaults so a test overrides only the
field it cares about — the goal is that every test reads like the scenario it
checks.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from agentic_calendar.contracts.common_types import AccountabilityStatus
from agentic_calendar.contracts.motivation_profile import (
    MotivationProfile,
    NudgeChannel,
    SponsorVisibility,
)
from agentic_calendar.contracts.sponsor import (
    Sponsor,
    SponsorRelationship,
    SponsorStatus,
)
from agentic_calendar.contracts.sponsor_report import (
    CompletionSummary,
    MilestoneStatus,
    SponsorReportInput,
    TaskCompletionSummary,
)

T0 = datetime(2026, 5, 10, 19, 0, 0, tzinfo=UTC)


def build_profile(**overrides: Any) -> MotivationProfile:
    """An accepted, summary-only sponsor profile by default."""
    base: dict[str, Any] = {
        "motivation_profile_id": "mot_1",
        "user_id": "user_123",
        "profile_version": "v1",
        "self_motivation_level": "medium",
        "procrastination_risk": "high",
        "pressure_tolerance": "medium",
        "weekly_checkin_enabled": False,
        "sponsor_enabled": True,
        "sponsor_visibility_level": SponsorVisibility.SUMMARY_ONLY,
        "sponsor_id": "sponsor_001",
        "created_at": T0,
        "updated_at": T0,
    }
    base.update(overrides)
    return MotivationProfile(**base)


def build_sponsor(**overrides: Any) -> Sponsor:
    """An accepted sponsor by default."""
    base: dict[str, Any] = {
        "sponsor_id": "sponsor_001",
        "user_id": "user_123",
        "relationship": SponsorRelationship.PARENT,
        "contact_channel": NudgeChannel.EMAIL,
        "status": SponsorStatus.ACCEPTED,
        "invited_at": T0,
        "accepted_at": T0,
        "created_at": T0,
        "updated_at": T0,
    }
    base.update(overrides)
    return Sponsor(**base)


def build_input(**overrides: Any) -> SponsorReportInput:
    """A slightly-behind progress snapshot with one milestone and task counts."""
    base: dict[str, Any] = {
        "user_id": "user_123",
        "plan_id": "plan_004",
        "status": AccountabilityStatus.SLIGHTLY_BEHIND,
        "completion_summary": CompletionSummary(
            completed_sessions=4, planned_sessions=6, on_track_percent=72
        ),
        "milestone_summary": [
            MilestoneStatus(milestone="Essay draft", status=AccountabilityStatus.BEHIND)
        ],
        "task_completion_summary": TaskCompletionSummary(completed_tasks=8, total_tasks=12),
        "candidate_suggested_support_action": "Ask the student to finish the outline.",
        "next_checkpoint_date": date(2026, 5, 17),
    }
    base.update(overrides)
    return SponsorReportInput(**base)
