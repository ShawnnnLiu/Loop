"""Guard the published confidence priors against accidental drift (axiom 08)."""

from __future__ import annotations

from agentic_calendar.contracts.source_claim import SourceType
from agentic_calendar.source_claims.priors import DEFAULT_CONFIDENCE_PRIORS as P


def test_base_scores_match_axiom_08() -> None:
    """The seven axiom-08 base scores, plus the canonical-topic-module addition."""
    assert dict(P.base_scores) == {
        SourceType.OFFICIAL_JOB_POSTING: 0.90,
        SourceType.COMPANY_ENGINEERING_BLOG: 0.75,
        SourceType.ROLE_TAXONOMY: 0.70,
        SourceType.INTERVIEW_POSTMORTEM: 0.65,
        SourceType.INTERVIEW_REPORT: 0.50,
        SourceType.PERSONAL_ANECDOTE: 0.35,
        SourceType.UNCLASSIFIED: 0.20,
        SourceType.CANONICAL_TOPIC_MODULE: 0.85,
    }


def test_every_source_type_has_a_base_and_expiry() -> None:
    for source_type in SourceType:
        assert source_type in P.base_scores
        assert source_type in P.expiry_days


def test_anecdotal_penalty_types() -> None:
    assert P.anecdotal_penalty_types == frozenset(
        {SourceType.PERSONAL_ANECDOTE, SourceType.UNCLASSIFIED}
    )
