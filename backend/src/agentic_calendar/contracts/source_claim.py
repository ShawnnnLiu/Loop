"""``source_claim`` contract.

Canonical spec: ``docs/specs/source-claim.schema.md`` (axiom 08).

A :class:`SourceClaim` is one atomic, auditable piece of retrieved evidence with
provenance, a deterministic confidence score, and an expiry. The Strategist
proposes curricula *against* these claims; it never produces one and never
assigns confidence.

Contract vs. kernel split (important):

* This module owns **shape and internal consistency**: the score is a number in
  ``[0, 1]``, the ``confidence_bucket`` matches the score (via
  :func:`bucket_for_score`, the single source of truth for the cutoffs), a claim
  never references itself, the corroborating/contradicting lists are disjoint,
  and ``expires_at`` is not before ``date_collected``.
* The ``source_claims`` kernel owns **production**: classification, the
  confidence formula, the bucket value, and ``expires_at`` are all *computed*
  deterministically at ingestion (``source_claims/ingestion.py``). Ingestion is
  the only sanctioned producer; an LLM may *explain* a claim but must never set
  its ``confidence_score`` / ``confidence_bucket`` (axiom 08). The contract only
  checks the *result* is consistent — the structural guarantee that "LLMs do not
  assign confidence" lives at ingestion, which recomputes and overwrites.

Atomicity ("a claim is acceptable/rejectable independently") is a semantic
property, not deterministically checkable; the contract enforces only
non-emptiness. It is a producer-side and review-side obligation.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SourceType(StrEnum):
    """Deterministic source classification (axiom 08 table).

    Classified by domain / URL rules (``source_claims/classification.py``),
    never by LLM judgment.
    """

    OFFICIAL_JOB_POSTING = "official_job_posting"
    COMPANY_ENGINEERING_BLOG = "company_engineering_blog"
    ROLE_TAXONOMY = "role_taxonomy"
    INTERVIEW_POSTMORTEM = "interview_postmortem"
    INTERVIEW_REPORT = "interview_report"
    PERSONAL_ANECDOTE = "personal_anecdote"
    UNCLASSIFIED = "unclassified"
    CANONICAL_TOPIC_MODULE = "canonical_topic_module"
    """Curated internal canonical content. Listed in axiom 08's expiration
    table (2+ years) but omitted from its base-score/classification tables;
    scored as a high-trust internal source (base 0.85) and never produced by
    URL classification — only by an internal curation path."""


class ConfidenceBucket(StrEnum):
    """Coarse confidence band derived from ``confidence_score`` (axiom 08)."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


#: Score at/above which a claim is ``high`` confidence (axiom 08).
HIGH_BUCKET_MIN = 0.80
#: Score at/above which a claim is at least ``medium`` confidence (axiom 08).
MEDIUM_BUCKET_MIN = 0.55


def bucket_for_score(score: float) -> ConfidenceBucket:
    """Map a confidence score to its bucket — the single source of truth.

    Cutoffs (axiom 08): ``high >= 0.80``, ``medium 0.55-0.79``, ``low < 0.55``.
    Imported by both the contract's consistency validator and the kernel scorer
    so the cutoffs are never re-derived in two places.
    """
    if score >= HIGH_BUCKET_MIN:
        return ConfidenceBucket.HIGH
    if score >= MEDIUM_BUCKET_MIN:
        return ConfidenceBucket.MEDIUM
    return ConfidenceBucket.LOW


class SourceClaim(BaseModel):
    """One auditable, deterministically-scored, expiring source claim."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    claim_id: str = Field(min_length=1)
    claim_text: str = Field(min_length=1)
    source_url: str = Field(min_length=1)
    source_type: SourceType
    date_collected: date
    source_published_date: date | None = None
    confidence_score: float = Field(ge=0.0, le=1.0)
    confidence_bucket: ConfidenceBucket
    expires_at: date
    corroborating_claim_ids: list[str] = Field(default_factory=list)
    contradicting_claim_ids: list[str] = Field(default_factory=list)

    def is_expired(self, now: datetime) -> bool:
        """Return ``True`` when the claim is at or past its expiry.

        Inclusive boundary (``expires_at <= now.date()``), matching every other
        expiry in the codebase (``approval_event`` / lock semantics). The single
        place this boundary is defined, so the kernel and the syllabus validator
        share one rule without crossing region boundaries.
        """
        return self.expires_at <= now.date()

    @model_validator(mode="after")
    def _bucket_matches_score(self) -> SourceClaim:
        expected = bucket_for_score(self.confidence_score)
        if self.confidence_bucket is not expected:
            raise ValueError(
                f"confidence_bucket {self.confidence_bucket.value!r} does not "
                f"match confidence_score {self.confidence_score} (expected "
                f"{expected.value!r})"
            )
        return self

    @model_validator(mode="after")
    def _no_self_reference(self) -> SourceClaim:
        if self.claim_id in self.corroborating_claim_ids:
            raise ValueError(
                f"claim_id {self.claim_id!r} cannot appear in its own "
                "corroborating_claim_ids"
            )
        if self.claim_id in self.contradicting_claim_ids:
            raise ValueError(
                f"claim_id {self.claim_id!r} cannot appear in its own "
                "contradicting_claim_ids"
            )
        return self

    @model_validator(mode="after")
    def _corroboration_contradiction_disjoint(self) -> SourceClaim:
        both = set(self.corroborating_claim_ids) & set(self.contradicting_claim_ids)
        if both:
            raise ValueError(
                "a claim id may not be in both corroborating_claim_ids and "
                f"contradicting_claim_ids: {sorted(both)}"
            )
        return self

    @model_validator(mode="after")
    def _expires_after_collected(self) -> SourceClaim:
        if self.expires_at < self.date_collected:
            raise ValueError(
                f"expires_at ({self.expires_at}) must not be before "
                f"date_collected ({self.date_collected})"
            )
        return self
