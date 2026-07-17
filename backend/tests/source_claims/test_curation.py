"""Tests for deterministic pre-prompt claim curation (UX pass D1b, plan 03§5)."""

from __future__ import annotations

from datetime import UTC, date, datetime

from agentic_calendar.contracts.source_claim import (
    SourceClaim,
    SourceType,
    bucket_for_score,
)
from agentic_calendar.source_claims.curation import (
    DEFAULT_CLAIM_CURATION_CONFIG,
    ClaimCurationConfig,
    curate_claims,
)

_NOW = datetime(2026, 7, 5, 12, 0, tzinfo=UTC)


def _claim(
    claim_id: str,
    *,
    confidence: float = 0.70,
    url: str = "https://engineering.acme.com/post",
    expires_at: date = date(2027, 1, 1),
) -> SourceClaim:
    return SourceClaim(
        claim_id=claim_id,
        claim_text="text",
        source_url=url,
        source_type=SourceType.COMPANY_ENGINEERING_BLOG,
        date_collected=date(2026, 6, 1),
        confidence_score=confidence,
        confidence_bucket=bucket_for_score(confidence),
        expires_at=expires_at,
    )


def test_expired_claims_dropped_inclusive_boundary() -> None:
    claims = [
        _claim("c_past", expires_at=date(2026, 7, 4)),
        _claim("c_today", expires_at=date(2026, 7, 5)),  # == now.date() → expired
        _claim("c_future", expires_at=date(2026, 7, 6)),
    ]
    result = curate_claims(claims, now=_NOW)
    assert [c.claim_id for c in result.kept] == ["c_future"]
    assert result.dropped_expired == ("c_past", "c_today")
    assert result.dropped_total == 2


def test_confidence_floor_drops_strictly_below_and_keeps_at_floor() -> None:
    floor = DEFAULT_CLAIM_CURATION_CONFIG.min_confidence
    claims = [
        _claim("c_at", confidence=floor),
        _claim("c_below", confidence=floor - 0.01),
        _claim("c_above", confidence=0.9),
    ]
    result = curate_claims(claims, now=_NOW)
    assert [c.claim_id for c in result.kept] == ["c_at", "c_above"]
    assert result.dropped_below_floor == ("c_below",)


def test_ingested_anecdote_score_survives_the_default_floor() -> None:
    """Axiom 08 admits anecdotes 'labeled low confidence'. A real ingested
    anecdote lands at 0.25 (0.35 base - 0.10 anecdotal penalty) — the exact
    score every anecdote in the first real store carried. The original 0.30
    floor was derived from the *base* and silently banned all of them; the
    2026-07-14 retune pins the floor at the post-penalty score."""
    anecdote = SourceClaim(
        claim_id="c_anecdote",
        claim_text="text",
        source_url="https://blog.example.com/my-interview",
        source_type=SourceType.PERSONAL_ANECDOTE,
        date_collected=date(2026, 6, 1),
        confidence_score=0.25,
        confidence_bucket=bucket_for_score(0.25),
        expires_at=date(2027, 1, 1),
    )
    result = curate_claims([anecdote], now=_NOW)
    assert [c.claim_id for c in result.kept] == ["c_anecdote"]


def test_uncorroborated_unclassified_score_stays_below_the_default_floor() -> None:
    """The floor's other documented intent: provenance-unknown claims need
    corroboration to appear. An ingested unclassified claim lands at 0.10
    (0.20 base - 0.10 penalty) and must not serve; only the saturated
    corroboration bonus (+0.15 → 0.25) lifts it to the floor."""
    def _unclassified(claim_id: str, score: float) -> SourceClaim:
        return SourceClaim(
            claim_id=claim_id,
            claim_text="text",
            source_url="https://plain.example.com/notes",
            source_type=SourceType.UNCLASSIFIED,
            date_collected=date(2026, 6, 1),
            confidence_score=score,
            confidence_bucket=bucket_for_score(score),
            expires_at=date(2027, 1, 1),
        )

    bare = _unclassified("c_bare", 0.10)
    corroborated = _unclassified("c_corroborated", 0.25)
    result = curate_claims([bare, corroborated], now=_NOW)
    assert [c.claim_id for c in result.kept] == ["c_corroborated"]
    assert result.dropped_below_floor == ("c_bare",)


def test_per_host_cap_keeps_highest_confidence_ties_by_claim_id() -> None:
    config = ClaimCurationConfig(max_per_host=2)
    claims = [
        _claim("c_weak", confidence=0.60),
        _claim("c_tie_b", confidence=0.80),
        _claim("c_strong", confidence=0.90),
        _claim("c_tie_a", confidence=0.80),
    ]
    result = curate_claims(claims, now=_NOW, config=config)
    # Survivors: c_strong (0.90) + c_tie_a (0.80, id tie-break) — kept order
    # preserves the input order, only the survivor CHOICE is ranked.
    assert [c.claim_id for c in result.kept] == ["c_strong", "c_tie_a"]
    assert result.dropped_over_host_cap == ("c_tie_b", "c_weak")


def test_per_host_cap_buckets_hosts_independently() -> None:
    config = ClaimCurationConfig(max_per_host=1)
    claims = [
        _claim("c_acme_1", url="https://engineering.acme.com/a", confidence=0.9),
        _claim("c_acme_2", url="https://engineering.acme.com/b", confidence=0.8),
        _claim("c_other", url="https://engineering.other.com/a", confidence=0.6),
    ]
    result = curate_claims(claims, now=_NOW, config=config)
    assert [c.claim_id for c in result.kept] == ["c_acme_1", "c_other"]
    assert result.dropped_over_host_cap == ("c_acme_2",)


def test_www_prefix_shares_a_bucket_with_the_bare_host() -> None:
    config = ClaimCurationConfig(max_per_host=1)
    claims = [
        _claim("c_bare", url="https://acme.com/a", confidence=0.9),
        _claim("c_www", url="https://www.acme.com/b", confidence=0.8),
    ]
    result = curate_claims(claims, now=_NOW, config=config)
    assert [c.claim_id for c in result.kept] == ["c_bare"]
    assert result.dropped_over_host_cap == ("c_www",)


def test_drop_reasons_are_disjoint_expiry_wins() -> None:
    """An expired, below-floor claim reports as expired only — every dropped
    id lands in exactly one reason bucket."""
    claims = [_claim("c_both", confidence=0.1, expires_at=date(2026, 7, 1))]
    result = curate_claims(claims, now=_NOW)
    assert result.dropped_expired == ("c_both",)
    assert result.dropped_below_floor == ()
    assert result.dropped_total == 1


def test_empty_input_yields_empty_result() -> None:
    result = curate_claims([], now=_NOW)
    assert result.kept == ()
    assert result.dropped_total == 0


def test_curation_is_deterministic_and_order_preserving() -> None:
    claims = [
        _claim("c_b", confidence=0.5),
        _claim("c_a", confidence=0.9, url="https://other.example.com/a"),
        _claim("c_c", confidence=0.7),
    ]
    first = curate_claims(claims, now=_NOW)
    second = curate_claims(claims, now=_NOW)
    assert first == second
    assert [c.claim_id for c in first.kept] == ["c_b", "c_a", "c_c"]
