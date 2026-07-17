"""Deterministic pre-prompt claim curation (plan 03 §5, UX pass D1b).

``_propose_fresh`` used to hand the Strategist *every* stored claim,
unfiltered. Expiry was enforced only by the post-generation syllabus
validator, so a stale ``claim_text`` could still steer generation and then
cost a full repair round when cited. This module filters the claim list
*before* it is serialized into the prompt:

1. **Expired claims** are dropped via ``SourceClaim.is_expired`` — the same
   inclusive boundary the syllabus validator applies (one rule, enforced at
   the prompt and again at validation).
2. **Confidence floor** on the stored deterministic ``confidence_score``.
   Scores are assigned at ingestion (axiom 08); this module never re-scores.
3. **Per-source-host cap**, highest confidence first. Company identity is
   not a contract field — it exists only at ingestion via operator-declared
   domains — so the ``source_url`` host is the deterministic proxy for the
   plan's "per company" cap. Subdomains are distinct buckets; claims whose
   URL has no recoverable host share one bucket.

This is a filter, not a ranking model: same inputs, same output, and kept
claims preserve their input order. Both knobs are UNCALIBRATED HEURISTIC
PRIORS (axiom 07/08 disclosure) — plausible, not optimal — registered as
the ``claim_curation`` tuning section so any change journals through the
threshold change log like every other deterministic knob.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from agentic_calendar.contracts.source_claim import SourceClaim

from .classification import _host


@dataclass(frozen=True)
class ClaimCurationConfig:
    """Curation knobs (heuristic, uncalibrated — see module docstring)."""

    min_confidence: float = 0.25
    """Floor on the stored ``confidence_score``.

    Set at the score a real ingested ``personal_anecdote`` actually lands on
    (0.35 base - 0.10 anecdotal penalty = 0.25), so labeled low-confidence
    anecdotes reach the prompt — axiom 08 admits them "only when labeled low
    confidence", not never — while ``unclassified`` claims (0.20 - 0.10 =
    0.10) need the full corroboration bonus (+0.15, three corroborators) to
    appear. The original D1b value (0.30) was derived from the anecdote
    *base* score and overlooked the penalty, silently banning every
    anecdote; retuned 2026-07-14 against the first real claim store (117
    claims: anecdotes uniformly 0.25, unclassified uniformly 0.10 — no
    published dates, no corroboration groups). Retuning the *penalty*
    instead was rejected: at 0.05 a maxed-out anecdote reaches 0.55, the
    ``medium`` bucket boundary, violating axiom 08's anecdotes-stay-``low``
    ceiling. Still a heuristic prior — the floor tracks today's uniform
    scores, not calibrated ground truth."""

    max_per_host: int = 5
    """Cap on claims sharing one source host, kept highest-confidence-first
    (ties broken by ``claim_id`` ascending). Enough for a real per-company
    signal without letting one heavily-scraped source flood the prompt."""


DEFAULT_CLAIM_CURATION_CONFIG = ClaimCurationConfig()


@dataclass(frozen=True)
class ClaimCurationResult:
    """Kept claims plus the dropped ids grouped by (typed) drop reason."""

    kept: tuple[SourceClaim, ...]
    dropped_expired: tuple[str, ...]
    dropped_below_floor: tuple[str, ...]
    dropped_over_host_cap: tuple[str, ...]

    @property
    def dropped_total(self) -> int:
        return (
            len(self.dropped_expired)
            + len(self.dropped_below_floor)
            + len(self.dropped_over_host_cap)
        )


def curate_claims(
    claims: Sequence[SourceClaim],
    *,
    now: datetime,
    config: ClaimCurationConfig = DEFAULT_CLAIM_CURATION_CONFIG,
) -> ClaimCurationResult:
    """Filter ``claims`` down to the set worth prompting with.

    Drop order is expiry → floor → host cap, so each id lands in exactly one
    reason bucket (an expired low-confidence claim reports as expired).
    ``kept`` preserves the caller's ordering; only the *choice* of survivors
    under the host cap is confidence-ranked.
    """
    expired: list[str] = []
    below_floor: list[str] = []
    survivors: list[SourceClaim] = []
    for claim in claims:
        if claim.is_expired(now):
            expired.append(claim.claim_id)
        elif claim.confidence_score < config.min_confidence:
            below_floor.append(claim.claim_id)
        else:
            survivors.append(claim)

    by_host: dict[str, list[SourceClaim]] = {}
    for claim in survivors:
        by_host.setdefault(_host(claim.source_url) or "", []).append(claim)
    over_cap: set[str] = set()
    for bucket in by_host.values():
        if len(bucket) <= config.max_per_host:
            continue
        ranked = sorted(bucket, key=lambda c: (-c.confidence_score, c.claim_id))
        over_cap.update(c.claim_id for c in ranked[config.max_per_host :])

    return ClaimCurationResult(
        kept=tuple(c for c in survivors if c.claim_id not in over_cap),
        dropped_expired=tuple(expired),
        dropped_below_floor=tuple(below_floor),
        dropped_over_host_cap=tuple(sorted(over_cap)),
    )
