"""Confidence-scoring priors — UNCALIBRATED HEURISTIC PRIORS (axiom 08).

Axiom 08 specifies the formula *structure* (``base + recency_bonus +
corroboration_bonus - anecdotal_penalty - contradiction_penalty -
stale_penalty``, clamped to ``[0, 1]``), the per-source-type **base scores**, the
bucket cutoffs, and an expiration-window **table** of ranges. It does **not**
specify the numeric magnitudes of the bonuses/penalties, the recency/staleness
time thresholds, or a single value inside each expiry range. Those are defined
here, and — exactly like ``drift/thresholds.py`` — every value was chosen to be
*plausible, not optimal*. They will be wrong for some claims and right for
others, and there is no data yet to know which.

Per axiom 08 ("Calibration Honesty"), the base scores and these magnitudes are
priors derived from heuristic judgment, not from data, and must be described as
heuristic until the calibration pass runs (>= 200 retrieved claims used in
production plans). Treat everything here as tunable, not ground truth.

Design choices worth recording:

* ``recency`` and ``corroboration`` caps are small (0.10 / 0.15) so they act as
  tiebreakers, never bucket-movers on their own. A fresh, triply-corroborated
  ``personal_anecdote`` (0.35 base) still ceilings at ``0.35 + 0.10 + 0.15 -
  0.10 = 0.50`` → ``low``, honouring axiom 08's "anecdotal reports only when
  labeled low confidence."
* ``anecdotal_penalty`` is *not* double-counting the low ``personal_anecdote``
  base: the base sets the centre of the band, the penalty caps the ceiling so a
  maxed-out anecdote cannot silently reach ``medium``.
* ``contradiction`` is the strongest negative signal (0.15/claim vs 0.05/claim
  for corroboration) so a couple of credible contradictions can drop even a
  fresh ``company_engineering_blog`` (≈0.85, high) to ``medium``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from agentic_calendar.contracts.source_claim import SourceType

#: Per-source-type base scores. Reproduces the axiom 08 table verbatim and adds
#: ``canonical_topic_module`` (curated internal content; just below an official
#: posting). This is the executable single source of truth for the base scores;
#: a test asserts it matches the axiom.
_BASE_SCORES: Mapping[SourceType, float] = MappingProxyType(
    {
        SourceType.OFFICIAL_JOB_POSTING: 0.90,
        SourceType.CANONICAL_TOPIC_MODULE: 0.85,
        SourceType.COMPANY_ENGINEERING_BLOG: 0.75,
        SourceType.ROLE_TAXONOMY: 0.70,
        SourceType.INTERVIEW_POSTMORTEM: 0.65,
        SourceType.INTERVIEW_REPORT: 0.50,
        SourceType.PERSONAL_ANECDOTE: 0.35,
        SourceType.UNCLASSIFIED: 0.20,
    }
)

#: Per-source-type expiry windows, in days. A single defensible value chosen
#: inside each axiom 08 range; windows the axiom leaves unspecified
#: (``interview_postmortem``, ``personal_anecdote``, ``unclassified``) are set
#: conservatively and flagged in the axiom doc.
_EXPIRY_DAYS: Mapping[SourceType, int] = MappingProxyType(
    {
        SourceType.OFFICIAL_JOB_POSTING: 45,  # axiom 30-60
        SourceType.INTERVIEW_REPORT: 120,  # axiom 90-180
        SourceType.INTERVIEW_POSTMORTEM: 120,  # axiom omits; reuse interview_report
        SourceType.ROLE_TAXONOMY: 180,  # axiom 180
        SourceType.COMPANY_ENGINEERING_BLOG: 540,  # axiom 365-730
        SourceType.PERSONAL_ANECDOTE: 90,  # axiom omits; anecdotes age fast
        SourceType.UNCLASSIFIED: 30,  # axiom omits; shortest, provenance unknown
        SourceType.CANONICAL_TOPIC_MODULE: 730,  # axiom "2+ years"
    }
)

#: Source types that carry the flat anecdotal penalty (weak provenance).
_ANECDOTAL_PENALTY_TYPES: frozenset[SourceType] = frozenset(
    {SourceType.PERSONAL_ANECDOTE, SourceType.UNCLASSIFIED}
)


@dataclass(frozen=True)
class ConfidencePriors:
    """Deterministic confidence-scoring priors (heuristic, uncalibrated)."""

    # ``MappingProxyType`` is unhashable, so a dataclass treats it as a mutable
    # default and forbids it; a factory returning the shared immutable instance
    # is the idiomatic workaround. ``frozenset`` is hashable and allowed direct.
    base_scores: Mapping[SourceType, float] = field(default_factory=lambda: _BASE_SCORES)
    expiry_days: Mapping[SourceType, int] = field(default_factory=lambda: _EXPIRY_DAYS)
    anecdotal_penalty_types: frozenset[SourceType] = _ANECDOTAL_PENALTY_TYPES

    # recency_bonus: f(age = now - source_published_date)
    recency_fresh_days: int = 30  # <= 30d old → full bonus
    recency_zero_days: int = 180  # >= 180d old → no bonus (linear ramp between)
    recency_bonus_max: float = 0.10

    # corroboration_bonus: f(len(corroborating_claim_ids))
    corroboration_per_claim: float = 0.05
    corroboration_max: float = 0.15  # saturates at 3 corroborators

    # anecdotal_penalty (flat, applied to anecdotal_penalty_types)
    anecdotal_penalty: float = 0.10

    # contradiction_penalty: f(len(contradicting_claim_ids))
    contradiction_per_claim: float = 0.15
    contradiction_max: float = 0.45  # saturates at 3 contradictors

    # stale_penalty: f(days until/ past expires_at)
    stale_ramp_days: int = 30  # within 30d of expiry → linear ramp up
    stale_penalty_at_expiry: float = 0.15  # penalty exactly at expires_at
    stale_penalty_max: float = 0.30  # cap once well past expiry


DEFAULT_CONFIDENCE_PRIORS = ConfidencePriors()
