"""Tests for the deterministic sponsor-report privacy filter (Phase 3)."""

from __future__ import annotations

from agentic_calendar.accountability.privacy_filter import PrivacyFilter
from agentic_calendar.contracts.motivation_profile import SponsorVisibility
from agentic_calendar.contracts.reason_codes import ReasonCode


def _clean_payload() -> dict[str, object]:
    return {
        "status": "slightly_behind",
        "completion_summary": {
            "completed_sessions": 4,
            "planned_sessions": 6,
            "on_track_percent": 72,
        },
        "milestone_summary": [{"milestone": "Essay draft", "status": "behind"}],
        "suggested_support_action": "Ask the student to finish the outline.",
    }


def test_clean_payload_passes() -> None:
    verdict = PrivacyFilter().scan(_clean_payload(), SponsorVisibility.SUMMARY_ONLY)
    assert verdict.ok is True
    assert verdict.reason_code is None
    assert verdict.offending_fields == ()


def test_denylisted_key_is_violation() -> None:
    payload = _clean_payload()
    payload["raw_calendar_title"] = "Therapy with Dr. Lee"
    verdict = PrivacyFilter().scan(payload, SponsorVisibility.SUMMARY_ONLY)
    assert verdict.ok is False
    assert verdict.reason_code is ReasonCode.SPONSOR_VISIBILITY_VIOLATION
    assert "raw_calendar_title" in verdict.offending_fields


def test_denylisted_key_matched_case_insensitively() -> None:
    payload = _clean_payload()
    payload["Private_Notes"] = "anything"
    verdict = PrivacyFilter().scan(payload, SponsorVisibility.SUMMARY_ONLY)
    assert verdict.ok is False
    assert "Private_Notes" in verdict.offending_fields


def test_marker_in_milestone_name_is_violation() -> None:
    payload = _clean_payload()
    payload["milestone_summary"] = [
        {"milestone": "Calendar Title: Therapy at 3pm", "status": "behind"}
    ]
    verdict = PrivacyFilter().scan(payload, SponsorVisibility.SUMMARY_ONLY)
    assert verdict.ok is False
    assert "milestone_summary" in verdict.offending_fields


def test_marker_in_suggested_action_is_violation() -> None:
    payload = _clean_payload()
    payload["suggested_support_action"] = "Diagnosis: anxiety; tell them to relax"
    verdict = PrivacyFilter().scan(payload, SponsorVisibility.SUMMARY_ONLY)
    assert verdict.ok is False
    assert "suggested_support_action" in verdict.offending_fields


def test_over_level_task_detail_is_violation_at_scan() -> None:
    payload = _clean_payload()
    payload["task_completion_summary"] = {"completed_tasks": 3, "total_tasks": 5}
    verdict = PrivacyFilter().scan(payload, SponsorVisibility.SUMMARY_ONLY)
    assert verdict.ok is False
    assert "task_completion_summary" in verdict.offending_fields


def test_task_detail_allowed_at_task_completion_level() -> None:
    payload = _clean_payload()
    payload["task_completion_summary"] = {"completed_tasks": 3, "total_tasks": 5}
    verdict = PrivacyFilter().scan(payload, SponsorVisibility.TASK_COMPLETION)
    assert verdict.ok is True


def test_strip_removes_over_level_field() -> None:
    payload = _clean_payload()
    payload["task_completion_summary"] = {"completed_tasks": 3, "total_tasks": 5}
    stripped = PrivacyFilter().strip_to_visibility(payload, SponsorVisibility.SUMMARY_ONLY)
    assert "task_completion_summary" not in stripped
    # Non-gated fields survive untouched.
    assert stripped["completion_summary"] == payload["completion_summary"]


def test_strip_keeps_task_detail_at_task_level() -> None:
    payload = _clean_payload()
    payload["task_completion_summary"] = {"completed_tasks": 3, "total_tasks": 5}
    stripped = PrivacyFilter().strip_to_visibility(payload, SponsorVisibility.TASK_COMPLETION)
    assert "task_completion_summary" in stripped


def test_extra_markers_are_configurable() -> None:
    payload = _clean_payload()
    payload["suggested_support_action"] = "secret-code-42 inside"
    base = PrivacyFilter()
    assert base.scan(payload, SponsorVisibility.SUMMARY_ONLY).ok is True
    extended = PrivacyFilter(extra_denylist_markers=["secret-code-42"])
    assert extended.scan(payload, SponsorVisibility.SUMMARY_ONLY).ok is False


def test_offending_fields_are_sorted_and_deduped() -> None:
    payload = _clean_payload()
    payload["essay_draft"] = "x"
    payload["health_info"] = "y"
    verdict = PrivacyFilter().scan(payload, SponsorVisibility.SUMMARY_ONLY)
    assert verdict.offending_fields == ("essay_draft", "health_info")
