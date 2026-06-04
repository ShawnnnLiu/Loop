"""Unit tests for ``canonical_sponsor_report_hash``.

Covers:
- Output format (``sha256:<64 hex>``)
- Determinism (identical reports produce identical hashes)
- Content sensitivity (each non-volatile field change produces a different hash)
- Volatile-field insensitivity (``generated_at``, ``trigger_reason_code``,
  ``requires_user_approval_before_send`` do NOT affect the hash)
- Milestone-list order sensitivity
- None-vs-value sensitivity for optional fields
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime

import pytest

from agentic_calendar.contracts.common_types import AccountabilityStatus
from agentic_calendar.contracts.motivation_profile import SponsorVisibility
from agentic_calendar.contracts.reason_codes import ReasonCode
from agentic_calendar.contracts.sponsor_report import (
    CompletionSummary,
    MilestoneStatus,
    SponsorReport,
    TaskCompletionSummary,
    canonical_sponsor_report_hash,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def _summary_report(**overrides: object) -> SponsorReport:
    """Return a valid SUMMARY_ONLY :class:`SponsorReport`, optionally overriding fields."""
    base = SponsorReport(
        report_id="rpt_1",
        user_id="user_1",
        sponsor_id="sponsor_1",
        plan_id="plan_1",
        visibility_level=SponsorVisibility.SUMMARY_ONLY,
        status=AccountabilityStatus.SLIGHTLY_BEHIND,
        completion_summary=CompletionSummary(
            completed_sessions=4,
            planned_sessions=6,
            on_track_percent=72,
        ),
        milestone_summary=[
            MilestoneStatus(milestone="Essay draft", status=AccountabilityStatus.BEHIND)
        ],
        suggested_support_action="Finish the outline",
        next_checkpoint_date=date(2026, 5, 17),
        trigger_reason_code=ReasonCode.SPONSOR_REPORT_PENDING,
        generated_at=datetime(2026, 5, 10, 19, tzinfo=UTC),
    )
    return base.model_copy(update=overrides)


def _task_report(**overrides: object) -> SponsorReport:
    """Return a valid TASK_COMPLETION :class:`SponsorReport`, optionally overriding fields."""
    base = SponsorReport(
        report_id="rpt_1",
        user_id="user_1",
        sponsor_id="sponsor_1",
        plan_id="plan_1",
        visibility_level=SponsorVisibility.TASK_COMPLETION,
        status=AccountabilityStatus.SLIGHTLY_BEHIND,
        completion_summary=CompletionSummary(
            completed_sessions=4,
            planned_sessions=6,
            on_track_percent=72,
        ),
        milestone_summary=[
            MilestoneStatus(milestone="Essay draft", status=AccountabilityStatus.BEHIND)
        ],
        task_completion_summary=TaskCompletionSummary(
            completed_tasks=8,
            total_tasks=12,
        ),
        suggested_support_action="Finish the outline",
        next_checkpoint_date=date(2026, 5, 17),
        trigger_reason_code=ReasonCode.SPONSOR_REPORT_PENDING,
        generated_at=datetime(2026, 5, 10, 19, tzinfo=UTC),
    )
    return base.model_copy(update=overrides)


# ---------------------------------------------------------------------------
# 1. Output format
# ---------------------------------------------------------------------------


def test_hash_format_matches_sha256_pattern() -> None:
    """Hash must match ``sha256:<64 hex digits>``."""
    h = canonical_sponsor_report_hash(_summary_report())
    assert _HASH_RE.match(h), f"hash {h!r} did not match expected pattern"


# ---------------------------------------------------------------------------
# 2. Determinism
# ---------------------------------------------------------------------------


def test_hash_is_deterministic_for_identical_reports() -> None:
    """Two independently constructed identical reports must hash equal."""
    report_a = _summary_report()
    report_b = _summary_report()
    assert canonical_sponsor_report_hash(report_a) == canonical_sponsor_report_hash(report_b)


# ---------------------------------------------------------------------------
# 3. Content sensitivity — each content field must change the hash
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field,new_value",
    [
        ("report_id", "rpt_DIFFERENT"),
        ("user_id", "user_DIFFERENT"),
        ("sponsor_id", "sponsor_DIFFERENT"),
        ("plan_id", "plan_DIFFERENT"),
        (
            "status",
            AccountabilityStatus.FAR_BEHIND,
        ),
        (
            "visibility_level",
            SponsorVisibility.MILESTONE_PROGRESS,
        ),
        (
            "completion_summary",
            CompletionSummary(
                completed_sessions=1,
                planned_sessions=6,
                on_track_percent=20,
            ),
        ),
        ("suggested_support_action", "A completely different action"),
        ("next_checkpoint_date", date(2026, 7, 1)),
    ],
    ids=[
        "report_id",
        "user_id",
        "sponsor_id",
        "plan_id",
        "status",
        "visibility_level",
        "completion_summary",
        "suggested_support_action",
        "next_checkpoint_date",
    ],
)
def test_content_field_change_produces_different_hash(field: str, new_value: object) -> None:
    """Changing a content field must produce a different hash."""
    base = _summary_report()
    altered = base.model_copy(update={field: new_value})
    assert canonical_sponsor_report_hash(base) != canonical_sponsor_report_hash(altered), (
        f"changing {field!r} should change the hash but did not"
    )


def test_milestone_name_change_produces_different_hash() -> None:
    """A milestone with a different name must change the hash."""
    base = _summary_report()
    altered = base.model_copy(
        update={
            "milestone_summary": [
                MilestoneStatus(milestone="DIFFERENT_MILESTONE", status=AccountabilityStatus.BEHIND)
            ]
        }
    )
    assert canonical_sponsor_report_hash(base) != canonical_sponsor_report_hash(altered)


def test_milestone_status_change_produces_different_hash() -> None:
    """A milestone with a different status must change the hash."""
    base = _summary_report()
    altered = base.model_copy(
        update={
            "milestone_summary": [
                MilestoneStatus(milestone="Essay draft", status=AccountabilityStatus.ON_TRACK)
            ]
        }
    )
    assert canonical_sponsor_report_hash(base) != canonical_sponsor_report_hash(altered)


def test_task_completion_summary_change_produces_different_hash() -> None:
    """Changing ``task_completion_summary`` on a TASK_COMPLETION report must change the hash."""
    base = _task_report()
    altered = base.model_copy(
        update={"task_completion_summary": TaskCompletionSummary(completed_tasks=1, total_tasks=12)}
    )
    assert canonical_sponsor_report_hash(base) != canonical_sponsor_report_hash(altered)


# ---------------------------------------------------------------------------
# 4. Volatile-field insensitivity — these must NOT change the hash
# ---------------------------------------------------------------------------


def test_different_generated_at_does_not_change_hash() -> None:
    """``generated_at`` is volatile and must not affect the hash."""
    base = _summary_report()
    altered = base.model_copy(update={"generated_at": datetime(2030, 1, 1, 0, 0, tzinfo=UTC)})
    assert canonical_sponsor_report_hash(base) == canonical_sponsor_report_hash(altered)


def test_different_trigger_reason_code_does_not_change_hash() -> None:
    """``trigger_reason_code`` is volatile and must not affect the hash."""
    base = _summary_report()
    altered = base.model_copy(update={"trigger_reason_code": ReasonCode.SPONSOR_PERMISSION_MISSING})
    assert canonical_sponsor_report_hash(base) == canonical_sponsor_report_hash(altered)


def test_requires_user_approval_before_send_flip_does_not_change_hash() -> None:
    """Flipping ``requires_user_approval_before_send`` must not change the hash."""
    # Default is True; flip to False.
    base = _summary_report(requires_user_approval_before_send=True)
    altered = base.model_copy(update={"requires_user_approval_before_send": False})
    assert canonical_sponsor_report_hash(base) == canonical_sponsor_report_hash(altered)


# ---------------------------------------------------------------------------
# 5. Milestone list order sensitivity
# ---------------------------------------------------------------------------


def test_milestone_order_affects_hash() -> None:
    """A report with milestones [A, B] must hash differently from [B, A]."""
    milestone_a = MilestoneStatus(milestone="Milestone A", status=AccountabilityStatus.ON_TRACK)
    milestone_b = MilestoneStatus(milestone="Milestone B", status=AccountabilityStatus.BEHIND)

    report_ab = _summary_report(milestone_summary=[milestone_a, milestone_b])
    report_ba = _summary_report(milestone_summary=[milestone_b, milestone_a])

    assert canonical_sponsor_report_hash(report_ab) != canonical_sponsor_report_hash(report_ba), (
        "milestone order must be part of the hash"
    )


# ---------------------------------------------------------------------------
# 6. None vs. value sensitivity for optional fields
# ---------------------------------------------------------------------------


def test_next_checkpoint_date_none_vs_date_differ() -> None:
    """``next_checkpoint_date=None`` must hash differently from an actual date."""
    with_none = _summary_report(next_checkpoint_date=None)
    with_date = _summary_report(next_checkpoint_date=date(2026, 5, 17))
    assert canonical_sponsor_report_hash(with_none) != canonical_sponsor_report_hash(with_date)


def test_suggested_support_action_none_vs_string_differ() -> None:
    """``suggested_support_action=None`` must hash differently from a non-empty string."""
    with_none = _summary_report(suggested_support_action=None)
    with_string = _summary_report(suggested_support_action="Finish the outline")
    assert canonical_sponsor_report_hash(with_none) != canonical_sponsor_report_hash(with_string)
