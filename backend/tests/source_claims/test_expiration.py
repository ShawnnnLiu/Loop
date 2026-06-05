"""Tests for claim expiration (axiom 08)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from agentic_calendar.contracts.source_claim import (
    ConfidenceBucket,
    SourceClaim,
    SourceType,
)
from agentic_calendar.source_claims.expiration import compute_expires_at, is_expired
from agentic_calendar.source_claims.priors import DEFAULT_CONFIDENCE_PRIORS as P


def test_compute_expires_at_per_source_type() -> None:
    anchor = date(2026, 1, 1)
    for source_type in SourceType:
        assert compute_expires_at(source_type, anchor=anchor) == anchor + timedelta(
            days=P.expiry_days[source_type]
        )


def _claim(expires_at: date) -> SourceClaim:
    return SourceClaim(
        claim_id="c",
        claim_text="t",
        source_url="https://x.example.com",
        source_type=SourceType.INTERVIEW_REPORT,
        date_collected=date(2026, 1, 1),
        confidence_score=0.6,
        confidence_bucket=ConfidenceBucket.MEDIUM,
        expires_at=expires_at,
    )


def test_is_expired_inclusive_boundary() -> None:
    now = datetime(2026, 6, 4, 12, 0, tzinfo=UTC)
    assert is_expired(_claim(date(2026, 6, 4)), now=now) is True  # == today
    assert is_expired(_claim(date(2026, 6, 3)), now=now) is True  # past
    assert is_expired(_claim(date(2026, 6, 5)), now=now) is False  # tomorrow
