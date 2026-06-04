"""Tests for ``SponsorReport``, ``SponsorReportInput``, and ``SponsorReportApproval``."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from agentic_calendar.contracts.sponsor_report import (
    SponsorReport,
    SponsorReportApproval,
    SponsorReportInput,
    canonical_sponsor_report_hash,
)
from tests._fixture_loader import iter_invalid, iter_valid

CONTRACT_SPONSOR_REPORT = "sponsor_report"
CONTRACT_SPONSOR_REPORT_INPUT = "sponsor_report_input"
CONTRACT_SPONSOR_REPORT_APPROVAL = "sponsor_report_approval"


# ---------------------------------------------------------------------------
# SponsorReport valid / invalid
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fixture",
    list(iter_valid(CONTRACT_SPONSOR_REPORT)),
    ids=lambda f: f.name,
)
def test_sponsor_report_valid_fixture_parses(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    report = SponsorReport.model_validate(payload)
    assert report.report_id == payload["report_id"]


@pytest.mark.parametrize(
    "fixture",
    list(iter_invalid(CONTRACT_SPONSOR_REPORT)),
    ids=lambda f: f.name,
)
def test_sponsor_report_invalid_fixture_rejected(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    expected = fixture.expected  # type: ignore[attr-defined]
    with pytest.raises(ValidationError) as exc_info:
        SponsorReport.model_validate(payload)
    msg = str(exc_info.value)
    for substr in expected["error_substrings"]:
        assert substr in msg, (
            f"expected substring {substr!r} not in error message:\n{msg}"
        )


# ---------------------------------------------------------------------------
# SponsorReportInput valid / invalid
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fixture",
    list(iter_valid(CONTRACT_SPONSOR_REPORT_INPUT)),
    ids=lambda f: f.name,
)
def test_sponsor_report_input_valid_fixture_parses(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    inp = SponsorReportInput.model_validate(payload)
    assert inp.user_id == payload["user_id"]


@pytest.mark.parametrize(
    "fixture",
    list(iter_invalid(CONTRACT_SPONSOR_REPORT_INPUT)),
    ids=lambda f: f.name,
)
def test_sponsor_report_input_invalid_fixture_rejected(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    expected = fixture.expected  # type: ignore[attr-defined]
    with pytest.raises(ValidationError) as exc_info:
        SponsorReportInput.model_validate(payload)
    msg = str(exc_info.value)
    for substr in expected["error_substrings"]:
        assert substr in msg, (
            f"expected substring {substr!r} not in error message:\n{msg}"
        )


# ---------------------------------------------------------------------------
# SponsorReportApproval valid / invalid
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fixture",
    list(iter_valid(CONTRACT_SPONSOR_REPORT_APPROVAL)),
    ids=lambda f: f.name,
)
def test_sponsor_report_approval_valid_fixture_parses(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    approval = SponsorReportApproval.model_validate(payload)
    assert approval.approval_event_id == payload["approval_event_id"]


@pytest.mark.parametrize(
    "fixture",
    list(iter_invalid(CONTRACT_SPONSOR_REPORT_APPROVAL)),
    ids=lambda f: f.name,
)
def test_sponsor_report_approval_invalid_fixture_rejected(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    expected = fixture.expected  # type: ignore[attr-defined]
    with pytest.raises(ValidationError) as exc_info:
        SponsorReportApproval.model_validate(payload)
    msg = str(exc_info.value)
    for substr in expected["error_substrings"]:
        assert substr in msg, (
            f"expected substring {substr!r} not in error message:\n{msg}"
        )


# ---------------------------------------------------------------------------
# canonical_sponsor_report_hash determinism and content sensitivity
# ---------------------------------------------------------------------------


def _build_base_report_payload() -> dict[str, object]:
    return {
        "report_id": "rpt_hash_test",
        "user_id": "user_001",
        "sponsor_id": "sponsor_001",
        "plan_id": "plan_001",
        "visibility_level": "summary_only",
        "status": "on_track",
        "completion_summary": {
            "completed_sessions": 8,
            "planned_sessions": 10,
            "on_track_percent": 80,
        },
        "milestone_summary": [],
        "task_completion_summary": None,
        "suggested_support_action": None,
        "next_checkpoint_date": None,
        "trigger_reason_code": "SPONSOR_REPORT_PENDING",
        "generated_at": "2026-05-15T10:00:00+00:00",
        "requires_user_approval_before_send": True,
    }


def test_canonical_hash_is_deterministic_and_content_sensitive() -> None:
    payload = _build_base_report_payload()

    report_a = SponsorReport.model_validate(payload)
    report_b = SponsorReport.model_validate(payload)

    hash_a = canonical_sponsor_report_hash(report_a)
    hash_b = canonical_sponsor_report_hash(report_b)

    # Identical content → identical hash
    assert hash_a == hash_b, "same content must produce the same hash"
    assert hash_a.startswith("sha256:"), "hash must begin with 'sha256:'"
    assert len(hash_a) == len("sha256:") + 64, "hash must be sha256:<64 hex chars>"

    # Change on_track_percent → hash must differ
    altered_payload = {
        **payload,
        "completion_summary": {
            "completed_sessions": 8,
            "planned_sessions": 10,
            "on_track_percent": 70,  # changed from 80
        },
    }
    report_c = SponsorReport.model_validate(altered_payload)
    hash_c = canonical_sponsor_report_hash(report_c)

    assert hash_a != hash_c, (
        "changed on_track_percent must produce a different hash"
    )
