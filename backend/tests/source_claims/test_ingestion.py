"""Tests for source-claim ingestion (axiom 08)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from agentic_calendar.common.clock import FrozenClock
from agentic_calendar.contracts.reason_codes import ReasonCode
from agentic_calendar.contracts.source_claim import SourceType
from agentic_calendar.source_claims.ingestion import (
    ClaimIngestionStatus,
    InMemorySourceClaimStore,
    SourceClaimAlreadyExistsError,
    SourceClaimIngestor,
)

NOW = datetime(2026, 6, 4, 12, 0, tzinfo=UTC)


def _ingestor() -> tuple[SourceClaimIngestor, InMemorySourceClaimStore]:
    store = InMemorySourceClaimStore()
    return SourceClaimIngestor(clock=FrozenClock(NOW), store=store), store


def test_ingest_overwrites_llm_supplied_derived_fields() -> None:
    """An LLM/scraper cannot set source_type/score/bucket/expiry — all recomputed."""
    ing, _ = _ingestor()
    out = ing.ingest(
        {
            "claim_id": "c1",
            "claim_text": "The role requires distributed systems experience.",
            "source_url": "https://boards.greenhouse.io/acme/jobs/1",
            "date_collected": "2026-06-01",
            # hostile/derived inputs that must be ignored:
            "source_type": "personal_anecdote",
            "confidence_score": 0.99,
            "confidence_bucket": "high",
            "expires_at": "2099-01-01",
        }
    )
    assert out.ok
    assert out.claim is not None
    # classified from the URL, not the supplied "personal_anecdote":
    assert out.claim.source_type is SourceType.OFFICIAL_JOB_POSTING
    assert out.claim.confidence_score != 0.99
    assert out.claim.expires_at.isoformat() != "2099-01-01"


def test_duplicate_is_idempotent() -> None:
    ing, store = _ingestor()
    raw = {
        "claim_id": "c1",
        "claim_text": "A verifiable claim.",
        "source_url": "https://x.example.com/a",
        "date_collected": "2026-06-01",
    }
    first = ing.ingest(raw)
    second = ing.ingest(raw)
    assert first.status is ClaimIngestionStatus.INGESTED
    assert second.status is ClaimIngestionStatus.DUPLICATE
    assert second.claim is not None and second.claim.claim_id == "c1"
    assert len(store.all()) == 1  # no second row


def test_rejected_on_malformed_claim_text() -> None:
    ing, _ = _ingestor()
    out = ing.ingest(
        {
            "claim_id": "c1",
            "claim_text": "",  # violates min_length
            "source_url": "https://x.example.com/a",
            "date_collected": "2026-06-01",
        }
    )
    assert out.status is ClaimIngestionStatus.REJECTED
    assert out.reason_code is ReasonCode.SCHEMA_INVALID
    assert out.claim is None


def test_rejected_when_source_url_missing() -> None:
    ing, _ = _ingestor()
    out = ing.ingest(
        {"claim_id": "c1", "claim_text": "x", "date_collected": "2026-06-01"}
    )
    assert out.status is ClaimIngestionStatus.REJECTED


def test_rejected_when_date_collected_missing() -> None:
    ing, _ = _ingestor()
    out = ing.ingest(
        {"claim_id": "c1", "claim_text": "x", "source_url": "https://x.example.com/a"}
    )
    assert out.status is ClaimIngestionStatus.REJECTED


def test_empty_corroboration_list_is_fine() -> None:
    ing, _ = _ingestor()
    out = ing.ingest(
        {
            "claim_id": "c1",
            "claim_text": "A verifiable claim.",
            "source_url": "https://x.example.com/a",
            "date_collected": "2026-06-01",
            "corroborating_claim_ids": [],
        }
    )
    assert out.ok


def test_ingest_uses_injected_company_context() -> None:
    """With company context, engineering blogs and careers domains are reachable
    (otherwise both fall through to unclassified)."""
    store = InMemorySourceClaimStore()
    ing = SourceClaimIngestor(
        clock=FrozenClock(NOW),
        store=store,
        known_company_domains=frozenset({"acme.com"}),
        engineering_blog_hosts=frozenset({"eng.acme.com"}),
    )
    blog = ing.ingest(
        {
            "claim_id": "b1",
            "claim_text": "Our interview emphasizes idempotent API design.",
            "source_url": "https://eng.acme.com/post",
            "date_collected": "2026-06-01",
        }
    )
    assert blog.claim is not None
    assert blog.claim.source_type is SourceType.COMPANY_ENGINEERING_BLOG

    careers = ing.ingest(
        {
            "claim_id": "j1",
            "claim_text": "The role requires distributed systems experience.",
            "source_url": "https://careers.acme.com/jobs/1",
            "date_collected": "2026-06-01",
        }
    )
    assert careers.claim is not None
    assert careers.claim.source_type is SourceType.OFFICIAL_JOB_POSTING


def test_ingest_curated_produces_canonical_topic_module() -> None:
    """The trusted curation path mints a source type URL classification can't —
    confidence/expiry still computed deterministically."""
    store = InMemorySourceClaimStore()
    ing = SourceClaimIngestor(clock=FrozenClock(NOW), store=store)
    out = ing.ingest_curated(
        {
            "claim_id": "t1",
            "claim_text": "Dynamic programming is a standard interview-prep module.",
            "source_url": "internal://canonical/topic/dynamic-programming",
            "date_collected": "2026-01-10",
            # a hostile confidence is still ignored on the curated path:
            "confidence_score": 0.99,
        },
        source_type=SourceType.CANONICAL_TOPIC_MODULE,
    )
    assert out.ok
    assert out.claim is not None
    assert out.claim.source_type is SourceType.CANONICAL_TOPIC_MODULE
    assert out.claim.expires_at == date(2026, 1, 10) + timedelta(days=730)
    assert out.claim.confidence_score == 0.85  # base, not the supplied 0.99


def test_corroboration_counts_only_store_resolved_references() -> None:
    """Phantom corroborator ids cannot inflate confidence; resolved ones do."""
    store = InMemorySourceClaimStore()
    ing = SourceClaimIngestor(clock=FrozenClock(NOW), store=store)

    phantom = ing.ingest(
        {
            "claim_id": "p1",
            "claim_text": "An interview report.",
            "source_url": "https://www.glassdoor.com/Interview/a",
            "date_collected": "2026-06-01",
            "corroborating_claim_ids": ["ghost1", "ghost2", "ghost3"],
        }
    )
    assert phantom.claim is not None
    assert phantom.claim.confidence_score == 0.50  # interview_report base, no bonus
    # but the full provided list is retained for audit:
    assert phantom.claim.corroborating_claim_ids == ["ghost1", "ghost2", "ghost3"]

    ing.ingest(
        {
            "claim_id": "real1",
            "claim_text": "A corroborating interview report.",
            "source_url": "https://www.glassdoor.com/Interview/b",
            "date_collected": "2026-06-01",
        }
    )
    corroborated = ing.ingest(
        {
            "claim_id": "c2",
            "claim_text": "An interview report corroborated by a stored claim.",
            "source_url": "https://www.glassdoor.com/Interview/c",
            "date_collected": "2026-06-01",
            "corroborating_claim_ids": ["real1"],
        }
    )
    assert corroborated.claim is not None
    assert corroborated.claim.confidence_score == 0.55  # 0.50 + 0.05 (one resolved)


def test_store_is_append_only() -> None:
    """A direct re-append of an existing id is an error (the ingestor dedups
    first, so this guards a direct caller)."""
    ing, store = _ingestor()
    out = ing.ingest(
        {
            "claim_id": "c1",
            "claim_text": "A verifiable claim.",
            "source_url": "https://x.example.com/a",
            "date_collected": "2026-06-01",
        }
    )
    assert out.claim is not None
    with pytest.raises(SourceClaimAlreadyExistsError):
        store.append(out.claim)
