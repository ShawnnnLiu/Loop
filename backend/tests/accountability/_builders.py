"""Tiny deterministic builders for accountability-region tests.

Kept under ``tests/`` (not ``src/``) as test-only infrastructure. Each builder
returns a fully valid object with sensible defaults so a test overrides only the
field it cares about — the goal is that every test reads like the scenario it
checks.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from agentic_calendar.contracts.accountability_contract import AccountabilityContract
from agentic_calendar.contracts.checkin_event import CheckinEvent
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
from agentic_calendar.contracts.telemetry import DataQuality, TelemetryEvent

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


def build_contract(**overrides: Any) -> AccountabilityContract:
    """An active, no-sponsor, check-ins-disabled contract with spec defaults."""
    base: dict[str, Any] = {
        "contract_id": "acct_1",
        "user_id": "user_123",
        "motivation_profile_id": "mot_1",
        "profile_version": "v1",
        "active": True,
        "weekly_checkin_enabled": False,
        "weekly_checkin_day": None,
        "weekly_checkin_time": None,
        "effective_missed_task_escalation_threshold": 2,
        "effective_behind_schedule_intervention_threshold_pct": 20,
        "low_completion_rate_floor": 0.5,
        "checkin_grace_hours": 48,
        "recovery_mode_preference": "reschedule",
        "sponsor_reporting_allowed": False,
        "sponsor_visibility_level": SponsorVisibility.NONE,
        "sponsor_id": None,
        "nudge_channel_preference": NudgeChannel.IN_APP,
        "quiet_hours": {"start": "22:00", "end": "08:00"},
        "created_at": T0,
        "updated_at": T0,
    }
    base.update(overrides)
    return AccountabilityContract(**base)


def build_telemetry_event(tid: str, **overrides: Any) -> TelemetryEvent:
    """A completed, fully-trusted execution record for ``tid``."""
    base: dict[str, Any] = {
        "telemetry_event_id": f"tel_{tid}",
        "task_id": tid,
        "scheduled_duration_min": 60,
        "actual_duration_min": 60,
        "completed": True,
        "completion_timestamp": T0,
        "user_reschedule_count": 0,
        "data_quality": DataQuality.COMPLETE,
    }
    base.update(overrides)
    if not base["completed"]:
        base["actual_duration_min"] = None
        base["completion_timestamp"] = None
    return TelemetryEvent(**base)


def build_checkin_event(**overrides: Any) -> CheckinEvent:
    """A submitted check-in for the week ending on T0's date."""
    base: dict[str, Any] = {
        "checkin_id": "checkin_1",
        "user_id": "user_123",
        "plan_id": "plan_004",
        "week_start": date(2026, 5, 4),
        "week_end": date(2026, 5, 10),
        "completed_task_count": 4,
        "scheduled_task_count": 6,
        "completed_minutes": 240,
        "scheduled_minutes": 360,
        "created_at": T0,
    }
    base.update(overrides)
    return CheckinEvent(**base)
