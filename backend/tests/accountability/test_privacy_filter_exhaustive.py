"""Exhaustive unit tests for the deterministic sponsor-report privacy filter.

Tests all public surface of:
  - PrivacyFilter (scan, strip_to_visibility, extra_denylist_markers)
  - PrivacyVerdict (ok, reason_code, offending_fields, violation classmethod)
  - Module constants: DENYLIST_KEYS, DEFAULT_DENYLIST_MARKERS
"""

from __future__ import annotations

import copy

import pytest

from agentic_calendar.accountability.privacy_filter import (
    DEFAULT_DENYLIST_MARKERS,
    DENYLIST_KEYS,
    PrivacyFilter,
    PrivacyVerdict,
)
from agentic_calendar.contracts.motivation_profile import SponsorVisibility
from agentic_calendar.contracts.reason_codes import ReasonCode

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _clean_payload() -> dict[str, object]:
    """A minimal sponsor payload that contains no denylisted content."""
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


# ---------------------------------------------------------------------------
# 1. Every denylisted key (lowercase) triggers a violation at SUMMARY_ONLY
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("key", sorted(DENYLIST_KEYS))
def test_denylist_key_lowercase_is_violation(key: str) -> None:
    payload = _clean_payload()
    payload[key] = "x"
    verdict = PrivacyFilter().scan(payload, SponsorVisibility.SUMMARY_ONLY)
    assert verdict.ok is False
    assert verdict.reason_code is ReasonCode.SPONSOR_VISIBILITY_VIOLATION
    assert key in verdict.offending_fields


# ---------------------------------------------------------------------------
# 2. Denylisted key UPPERCASED in payload still triggers (case-insensitive)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("key", sorted(DENYLIST_KEYS))
def test_denylist_key_uppercased_is_violation(key: str) -> None:
    payload = _clean_payload()
    upper_key = key.upper()
    payload[upper_key] = "x"
    verdict = PrivacyFilter().scan(payload, SponsorVisibility.SUMMARY_ONLY)
    assert verdict.ok is False
    assert verdict.reason_code is ReasonCode.SPONSOR_VISIBILITY_VIOLATION
    assert upper_key in verdict.offending_fields


# ---------------------------------------------------------------------------
# 3. Each DEFAULT_DENYLIST_MARKER embedded in suggested_support_action
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("marker", DEFAULT_DENYLIST_MARKERS)
def test_marker_in_suggested_support_action_is_violation(marker: str) -> None:
    payload = _clean_payload()
    payload["suggested_support_action"] = f"prefix {marker} suffix"
    verdict = PrivacyFilter().scan(payload, SponsorVisibility.SUMMARY_ONLY)
    assert verdict.ok is False
    assert verdict.reason_code is ReasonCode.SPONSOR_VISIBILITY_VIOLATION
    assert "suggested_support_action" in verdict.offending_fields


# ---------------------------------------------------------------------------
# 4. Each DEFAULT_DENYLIST_MARKER embedded inside a milestone name
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("marker", DEFAULT_DENYLIST_MARKERS)
def test_marker_in_milestone_name_is_violation(marker: str) -> None:
    payload = _clean_payload()
    payload["milestone_summary"] = [{"milestone": f"Goal: {marker}", "status": "on_track"}]
    verdict = PrivacyFilter().scan(payload, SponsorVisibility.SUMMARY_ONLY)
    assert verdict.ok is False
    assert verdict.reason_code is ReasonCode.SPONSOR_VISIBILITY_VIOLATION
    assert "milestone_summary" in verdict.offending_fields


# ---------------------------------------------------------------------------
# 5. suggested_support_action=None → clean (no false positive)
# ---------------------------------------------------------------------------


def test_suggested_support_action_none_is_clean() -> None:
    payload = _clean_payload()
    payload["suggested_support_action"] = None
    verdict = PrivacyFilter().scan(payload, SponsorVisibility.SUMMARY_ONLY)
    assert verdict.ok is True
    assert verdict.reason_code is None
    assert verdict.offending_fields == ()


# ---------------------------------------------------------------------------
# 6. Non-string scalar in a text field does not raise and is clean
# ---------------------------------------------------------------------------


def test_non_string_scalar_in_text_field_is_clean() -> None:
    payload = _clean_payload()
    payload["suggested_support_action"] = 123
    # Must not raise; must not produce a false violation.
    verdict = PrivacyFilter().scan(payload, SponsorVisibility.SUMMARY_ONLY)
    assert verdict.ok is True
    assert verdict.offending_fields == ()


# ---------------------------------------------------------------------------
# 7. Empty dict payload → clean
# ---------------------------------------------------------------------------


def test_empty_payload_is_clean() -> None:
    verdict = PrivacyFilter().scan({}, SponsorVisibility.SUMMARY_ONLY)
    assert verdict.ok is True
    assert verdict.reason_code is None
    assert verdict.offending_fields == ()


# ---------------------------------------------------------------------------
# 8. Marker inside milestone name only (status is clean) + deeply nested list
# ---------------------------------------------------------------------------


def test_marker_in_nested_milestone_with_clean_status_is_detected() -> None:
    marker = DEFAULT_DENYLIST_MARKERS[0]  # "calendar title:"
    payload = _clean_payload()
    # Deeply nested list: a list of lists containing milestone dicts.
    payload["milestone_summary"] = [[{"milestone": f"section: {marker}", "status": "ahead"}]]
    verdict = PrivacyFilter().scan(payload, SponsorVisibility.SUMMARY_ONLY)
    assert verdict.ok is False
    assert "milestone_summary" in verdict.offending_fields


# ---------------------------------------------------------------------------
# 9. strip_to_visibility does NOT mutate its input
# ---------------------------------------------------------------------------


def test_strip_does_not_mutate_input() -> None:
    payload = _clean_payload()
    payload["task_completion_summary"] = {"completed_tasks": 2, "total_tasks": 5}
    before = copy.deepcopy(payload)
    PrivacyFilter().strip_to_visibility(payload, SponsorVisibility.SUMMARY_ONLY)
    assert payload == before


# ---------------------------------------------------------------------------
# 10. strip_to_visibility is idempotent
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "visibility",
    [SponsorVisibility.SUMMARY_ONLY, SponsorVisibility.TASK_COMPLETION],
)
def test_strip_is_idempotent(visibility: SponsorVisibility) -> None:
    payload = _clean_payload()
    payload["task_completion_summary"] = {"completed_tasks": 2, "total_tasks": 5}
    pf = PrivacyFilter()
    once = pf.strip_to_visibility(payload, visibility)
    twice = pf.strip_to_visibility(once, visibility)
    assert once == twice


# ---------------------------------------------------------------------------
# 11. task_completion_summary field gating at each visibility level
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "visibility",
    [
        SponsorVisibility.NONE,
        SponsorVisibility.SUMMARY_ONLY,
        SponsorVisibility.MILESTONE_PROGRESS,
    ],
)
def test_task_completion_summary_removed_below_task_completion(
    visibility: SponsorVisibility,
) -> None:
    payload = _clean_payload()
    payload["task_completion_summary"] = {"completed_tasks": 3, "total_tasks": 6}
    stripped = PrivacyFilter().strip_to_visibility(payload, visibility)
    assert "task_completion_summary" not in stripped


def test_task_completion_summary_kept_at_task_completion() -> None:
    payload = _clean_payload()
    task_detail = {"completed_tasks": 3, "total_tasks": 6}
    payload["task_completion_summary"] = task_detail
    stripped = PrivacyFilter().strip_to_visibility(payload, SponsorVisibility.TASK_COMPLETION)
    assert "task_completion_summary" in stripped
    assert stripped["task_completion_summary"] == task_detail


# ---------------------------------------------------------------------------
# 12. extra_denylist_markers: custom marker only detected when configured
# ---------------------------------------------------------------------------


def test_extra_denylist_marker_not_detected_by_default() -> None:
    custom_marker = "xyzzy-secret-marker"
    payload = _clean_payload()
    payload["suggested_support_action"] = f"prefix {custom_marker} suffix"
    verdict = PrivacyFilter().scan(payload, SponsorVisibility.SUMMARY_ONLY)
    # Default filter must not flag it.
    assert verdict.ok is True


def test_extra_denylist_marker_detected_when_configured() -> None:
    custom_marker = "xyzzy-secret-marker"
    payload = _clean_payload()
    payload["suggested_support_action"] = f"prefix {custom_marker} suffix"
    pf = PrivacyFilter(extra_denylist_markers=[custom_marker])
    verdict = pf.scan(payload, SponsorVisibility.SUMMARY_ONLY)
    assert verdict.ok is False
    assert verdict.reason_code is ReasonCode.SPONSOR_VISIBILITY_VIOLATION
    assert "suggested_support_action" in verdict.offending_fields


def test_extra_denylist_marker_case_insensitive() -> None:
    """Custom marker registered as lowercase, detected even when payload is uppercase."""
    custom_marker = "top-secret"
    payload = _clean_payload()
    payload["suggested_support_action"] = "TOP-SECRET details inside"
    pf = PrivacyFilter(extra_denylist_markers=[custom_marker])
    verdict = pf.scan(payload, SponsorVisibility.SUMMARY_ONLY)
    assert verdict.ok is False
    assert "suggested_support_action" in verdict.offending_fields


# ---------------------------------------------------------------------------
# 13. PrivacyVerdict.violation deduplicates and sorts offending fields
# ---------------------------------------------------------------------------


def test_violation_deduplicates_and_sorts_offending_fields() -> None:
    # Provide duplicates and unsorted order.
    raw = ["zzz_field", "aaa_field", "mmm_field", "aaa_field", "zzz_field"]
    verdict = PrivacyVerdict.violation(raw)
    assert verdict.ok is False
    assert verdict.reason_code is ReasonCode.SPONSOR_VISIBILITY_VIOLATION
    assert verdict.offending_fields == ("aaa_field", "mmm_field", "zzz_field")


def test_violation_single_field_tuple() -> None:
    verdict = PrivacyVerdict.violation(["only_field"])
    assert verdict.offending_fields == ("only_field",)


def test_violation_with_empty_iterable() -> None:
    # Degenerate: no offending fields but called as violation.
    verdict = PrivacyVerdict.violation([])
    assert verdict.ok is False
    assert verdict.offending_fields == ()


# ---------------------------------------------------------------------------
# Additional edge-case tests
# ---------------------------------------------------------------------------


def test_clean_verdict_fields() -> None:
    verdict = PrivacyVerdict.clean()
    assert verdict.ok is True
    assert verdict.reason_code is None
    assert verdict.offending_fields == ()


def test_multiple_denylist_keys_all_reported() -> None:
    """Two denylisted keys both appear in offending_fields, sorted."""
    payload = _clean_payload()
    payload["essay_draft"] = "some text"
    payload["health_info"] = "personal data"
    verdict = PrivacyFilter().scan(payload, SponsorVisibility.SUMMARY_ONLY)
    assert verdict.ok is False
    assert "essay_draft" in verdict.offending_fields
    assert "health_info" in verdict.offending_fields
    # Must be sorted.
    assert verdict.offending_fields == tuple(sorted(verdict.offending_fields))


def test_task_completion_summary_none_at_summary_only_is_clean() -> None:
    """A None-valued task_completion_summary should NOT trigger a level violation."""
    payload = _clean_payload()
    payload["task_completion_summary"] = None
    verdict = PrivacyFilter().scan(payload, SponsorVisibility.SUMMARY_ONLY)
    # The scan code guards: `payload[key] is not None` before flagging.
    assert verdict.ok is True


def test_marker_in_milestone_status_is_also_detected() -> None:
    """A marker buried inside the status value of a milestone dict is detected."""
    marker = DEFAULT_DENYLIST_MARKERS[2]  # "private note:"
    payload = _clean_payload()
    payload["milestone_summary"] = [{"milestone": "normal", "status": f"status {marker}"}]
    verdict = PrivacyFilter().scan(payload, SponsorVisibility.SUMMARY_ONLY)
    assert verdict.ok is False
    assert "milestone_summary" in verdict.offending_fields


def test_strip_non_gated_fields_pass_through_unchanged() -> None:
    """Fields not in _LEVEL_GATED_FIELDS are always preserved by strip."""
    payload = _clean_payload()
    stripped = PrivacyFilter().strip_to_visibility(payload, SponsorVisibility.NONE)
    # All clean-payload keys are non-gated and must survive.
    for key in _clean_payload():
        assert key in stripped
        assert stripped[key] == payload[key]


def test_scan_at_task_completion_level_allows_task_detail() -> None:
    payload = _clean_payload()
    payload["task_completion_summary"] = {"done": 4, "total": 5}
    verdict = PrivacyFilter().scan(payload, SponsorVisibility.TASK_COMPLETION)
    assert verdict.ok is True


def test_scan_at_milestone_progress_flags_task_detail() -> None:
    """task_completion_summary is not allowed at MILESTONE_PROGRESS via scan."""
    payload = _clean_payload()
    payload["task_completion_summary"] = {"done": 1, "total": 3}
    verdict = PrivacyFilter().scan(payload, SponsorVisibility.MILESTONE_PROGRESS)
    assert verdict.ok is False
    assert "task_completion_summary" in verdict.offending_fields


def test_marker_upper_in_suggested_action_is_detected() -> None:
    """Markers matched case-insensitively in free-text fields."""
    marker = DEFAULT_DENYLIST_MARKERS[0].upper()  # "CALENDAR TITLE:"
    payload = _clean_payload()
    payload["suggested_support_action"] = f"Please see {marker} notes"
    verdict = PrivacyFilter().scan(payload, SponsorVisibility.SUMMARY_ONLY)
    assert verdict.ok is False
    assert "suggested_support_action" in verdict.offending_fields


def test_strip_returns_new_dict_not_same_object() -> None:
    """strip_to_visibility must return a new dict, not a reference to the input."""
    payload = _clean_payload()
    result = PrivacyFilter().strip_to_visibility(payload, SponsorVisibility.TASK_COMPLETION)
    assert result is not payload
