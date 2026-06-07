"""Deterministic confidence scoring (axiom 08).

Pure functions only: the score is a function of the claim's fields plus an
injected ``now`` (the current time, from a ``Clock``). No randomness, no
wall-clock reads, no LLM. The formula, in axiom order::

    confidence = base
                 + recency_bonus
                 + corroboration_bonus
                 - anecdotal_penalty
                 - contradiction_penalty
                 - stale_penalty

clamped to ``[0, 1]`` and rounded to 2 dp (byte-stable JSON, matching
``drift/classifier.py``). The bucket is derived from the score via
``bucket_for_score`` — the kernel never re-derives the cutoffs.

Every magnitude lives in ``priors.py`` and is an uncalibrated heuristic prior.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime

from agentic_calendar.contracts.source_claim import SourceType

from .priors import DEFAULT_CONFIDENCE_PRIORS, ConfidencePriors


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _recency_bonus(
    source_published_date: date | None, now: datetime, priors: ConfidencePriors
) -> float:
    """Full bonus when fresh, linear decay to zero at ``recency_zero_days``.

    ``None`` publication date earns no bonus — unknown freshness is not rewarded.
    """
    if source_published_date is None:
        return 0.0
    age_days = (now.date() - source_published_date).days
    if age_days <= priors.recency_fresh_days:
        return priors.recency_bonus_max
    if age_days >= priors.recency_zero_days:
        return 0.0
    span = priors.recency_zero_days - priors.recency_fresh_days
    frac = (priors.recency_zero_days - age_days) / span
    return priors.recency_bonus_max * frac


def _corroboration_bonus(count: int, priors: ConfidencePriors) -> float:
    return min(priors.corroboration_per_claim * count, priors.corroboration_max)


def _anecdotal_penalty(source_type: SourceType, priors: ConfidencePriors) -> float:
    return (
        priors.anecdotal_penalty
        if source_type in priors.anecdotal_penalty_types
        else 0.0
    )


def _contradiction_penalty(count: int, priors: ConfidencePriors) -> float:
    return min(priors.contradiction_per_claim * count, priors.contradiction_max)


def _stale_penalty(
    expires_at: date, now: datetime, priors: ConfidencePriors
) -> float:
    """Smoothly degrade confidence as a claim nears and passes its expiry.

    This is *separate* from the hard expiry boolean (``SourceClaim.is_expired``):
    the penalty makes near-expiry claims rank lower; the boolean makes expired
    claims ineligible to drive generation. Two mechanisms, deliberately.
    """
    days_to_expiry = (expires_at - now.date()).days
    if days_to_expiry > priors.stale_ramp_days:
        return 0.0
    if days_to_expiry >= 0:
        frac = 1.0 - (days_to_expiry / priors.stale_ramp_days)
        return priors.stale_penalty_at_expiry * frac
    overdue = -days_to_expiry
    extra = (overdue / priors.stale_ramp_days) * (
        priors.stale_penalty_max - priors.stale_penalty_at_expiry
    )
    return min(priors.stale_penalty_at_expiry + extra, priors.stale_penalty_max)


def score_confidence(
    *,
    source_type: SourceType,
    source_published_date: date | None,
    expires_at: date,
    corroborating_claim_ids: Sequence[str],
    contradicting_claim_ids: Sequence[str],
    now: datetime,
    priors: ConfidencePriors = DEFAULT_CONFIDENCE_PRIORS,
) -> float:
    """Return the deterministic confidence score in ``[0, 1]`` (2 dp)."""
    raw = (
        priors.base_scores[source_type]
        + _recency_bonus(source_published_date, now, priors)
        + _corroboration_bonus(len(corroborating_claim_ids), priors)
        - _anecdotal_penalty(source_type, priors)
        - _contradiction_penalty(len(contradicting_claim_ids), priors)
        - _stale_penalty(expires_at, now, priors)
    )
    return round(_clamp01(raw), 2)
