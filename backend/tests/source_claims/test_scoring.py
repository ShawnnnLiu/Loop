"""Tests for the deterministic confidence formula (axiom 08)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta

import pytest

from agentic_calendar.contracts.source_claim import (
    ConfidenceBucket,
    SourceType,
    bucket_for_score,
)
from agentic_calendar.source_claims.priors import DEFAULT_CONFIDENCE_PRIORS as P
from agentic_calendar.source_claims.scoring import score_confidence

NOW = datetime(2026, 6, 4, 12, 0, tzinfo=UTC)
TODAY = NOW.date()
FAR = TODAY + timedelta(days=365)  # well beyond the stale ramp → no stale penalty


def _score(
    source_type: SourceType,
    *,
    published: date | None = None,
    expires_at: date = FAR,
    corr: int = 0,
    contra: int = 0,
) -> float:
    corroborating: Sequence[str] = ["x"] * corr
    contradicting: Sequence[str] = ["y"] * contra
    return score_confidence(
        source_type=source_type,
        source_published_date=published,
        expires_at=expires_at,
        corroborating_claim_ids=corroborating,
        contradicting_claim_ids=contradicting,
        now=NOW,
    )


@pytest.mark.parametrize("source_type", list(SourceType))
def test_neutral_score_is_base_minus_anecdotal(source_type: SourceType) -> None:
    """Every source type at neutral inputs returns its base (less any flat
    anecdotal penalty). This pins the executable base table to axiom 08."""
    penalty = (
        P.anecdotal_penalty if source_type in P.anecdotal_penalty_types else 0.0
    )
    assert _score(source_type) == round(max(0.0, P.base_scores[source_type] - penalty), 2)


def test_recency_bonus_ramp() -> None:
    st = SourceType.INTERVIEW_REPORT  # base 0.50
    assert _score(st, published=TODAY - timedelta(days=10)) == 0.60  # full +0.10
    assert _score(st, published=TODAY - timedelta(days=105)) == 0.55  # half ramp
    assert _score(st, published=TODAY - timedelta(days=200)) == 0.50  # decayed to 0
    assert _score(st, published=None) == 0.50  # unknown freshness → no bonus


def test_corroboration_bonus_caps() -> None:
    st = SourceType.INTERVIEW_REPORT
    assert _score(st, corr=1) == 0.55
    assert _score(st, corr=3) == 0.65
    assert _score(st, corr=5) == 0.65  # saturates at the 0.15 cap


def test_contradiction_penalty_caps() -> None:
    st = SourceType.COMPANY_ENGINEERING_BLOG  # base 0.75
    assert _score(st, contra=1) == 0.60
    assert _score(st, contra=2) == 0.45
    assert _score(st, contra=4) == 0.30  # saturates at the 0.45 cap


def test_anecdote_ceiling_stays_low() -> None:
    """A maxed-out anecdote (fresh + corroborated) still cannot reach medium."""
    s = _score(SourceType.PERSONAL_ANECDOTE, published=TODAY - timedelta(days=5), corr=3)
    assert s == 0.50
    assert bucket_for_score(s) is ConfidenceBucket.LOW


def test_stale_penalty() -> None:
    st = SourceType.INTERVIEW_REPORT  # base 0.50
    assert _score(st, expires_at=TODAY + timedelta(days=90)) == 0.50  # far → none
    assert _score(st, expires_at=TODAY) == 0.35  # exactly at expiry → -0.15
    assert _score(st, expires_at=TODAY - timedelta(days=30)) == 0.20  # past → -0.30 cap


def test_clamp_high() -> None:
    s = _score(SourceType.OFFICIAL_JOB_POSTING, published=TODAY - timedelta(days=5), corr=3)
    assert s == 1.0  # 0.90 + 0.10 + 0.15 = 1.15 → clamped
    assert bucket_for_score(s) is ConfidenceBucket.HIGH


def test_clamp_low() -> None:
    s = _score(
        SourceType.UNCLASSIFIED, expires_at=TODAY - timedelta(days=60), contra=3
    )
    assert s == 0.0  # 0.20 - 0.10 - 0.45 - 0.30 = -0.65 → clamped
    assert bucket_for_score(s) is ConfidenceBucket.LOW


def test_contradiction_drops_bucket_high_to_medium() -> None:
    fresh = _score(SourceType.COMPANY_ENGINEERING_BLOG, published=TODAY - timedelta(days=5))
    contradicted = _score(
        SourceType.COMPANY_ENGINEERING_BLOG,
        published=TODAY - timedelta(days=5),
        contra=2,
    )
    assert bucket_for_score(fresh) is ConfidenceBucket.HIGH  # 0.85
    assert bucket_for_score(contradicted) is ConfidenceBucket.MEDIUM  # 0.55


def test_determinism() -> None:
    kwargs = {"published": TODAY - timedelta(days=20), "corr": 2, "contra": 1}
    a = _score(SourceType.INTERVIEW_REPORT, **kwargs)  # type: ignore[arg-type]
    b = _score(SourceType.INTERVIEW_REPORT, **kwargs)  # type: ignore[arg-type]
    assert a == b
