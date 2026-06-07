"""Tests for the ``SourceClaim`` contract and its bucket/expiry helpers."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from agentic_calendar.contracts.source_claim import (
    ConfidenceBucket,
    SourceClaim,
    SourceType,
    bucket_for_score,
)
from tests._fixture_loader import iter_invalid, iter_valid

CONTRACT = "source_claim"


@pytest.mark.parametrize("fixture", list(iter_valid(CONTRACT)), ids=lambda f: f.name)
def test_valid_fixture_parses(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    claim = SourceClaim.model_validate(payload)
    assert claim.claim_id == payload["claim_id"]


@pytest.mark.parametrize("fixture", list(iter_invalid(CONTRACT)), ids=lambda f: f.name)
def test_invalid_fixture_rejected(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    expected = fixture.expected  # type: ignore[attr-defined]
    with pytest.raises(ValidationError) as exc_info:
        SourceClaim.model_validate(payload)
    msg = str(exc_info.value)
    for substr in expected["error_substrings"]:
        assert substr in msg, f"expected substring {substr!r} not in:\n{msg}"


@pytest.mark.parametrize(
    ("score", "bucket"),
    [
        (1.0, ConfidenceBucket.HIGH),
        (0.80, ConfidenceBucket.HIGH),
        (0.7999, ConfidenceBucket.MEDIUM),
        (0.55, ConfidenceBucket.MEDIUM),
        (0.5499, ConfidenceBucket.LOW),
        (0.0, ConfidenceBucket.LOW),
    ],
)
def test_bucket_for_score_cutoffs(score: float, bucket: ConfidenceBucket) -> None:
    """The off-by-one boundaries at 0.80 and 0.55 (axiom 08)."""
    assert bucket_for_score(score) is bucket


def _claim(*, expires_at: date) -> SourceClaim:
    return SourceClaim(
        claim_id="c",
        claim_text="text",
        source_url="https://example.com/x",
        source_type=SourceType.INTERVIEW_REPORT,
        date_collected=date(2026, 1, 1),
        confidence_score=0.6,
        confidence_bucket=ConfidenceBucket.MEDIUM,
        expires_at=expires_at,
    )


def test_is_expired_inclusive_boundary() -> None:
    now = datetime(2026, 6, 4, 9, 0, tzinfo=UTC)
    assert _claim(expires_at=date(2026, 6, 4)).is_expired(now) is True  # == today
    assert _claim(expires_at=date(2026, 6, 3)).is_expired(now) is True  # past
    assert _claim(expires_at=date(2026, 6, 5)).is_expired(now) is False  # future
