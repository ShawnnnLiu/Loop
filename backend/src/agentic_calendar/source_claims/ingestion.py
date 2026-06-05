"""Source-claim ingestion (Phase 5).

Turns a raw retrieved record into a validated, stored :class:`SourceClaim`,
deterministically. This is the **only sanctioned producer** of a claim's
``source_type`` / ``confidence_score`` / ``confidence_bucket`` / ``expires_at``:
any of those fields present in the raw payload are stripped and recomputed, so an
LLM or scraper can never assign confidence (axiom 08).

Two entry points:

* :meth:`SourceClaimIngestor.ingest` — for *retrieved* claims. ``source_type`` is
  derived by URL classification. The constructor may be given
  ``known_company_domains`` / ``engineering_blog_hosts`` so a composition root can
  supply company context (otherwise non-enumerable hosts fall through to
  ``unclassified``, honestly).
* :meth:`SourceClaimIngestor.ingest_curated` — for internally *curated* content
  (e.g. ``canonical_topic_module``) whose provenance is trusted and known. The
  caller declares the ``source_type``; confidence/expiry are still computed
  deterministically (the caller never sets confidence). This is the "internal
  curation path" referenced by ``SourceType.CANONICAL_TOPIC_MODULE``.

Pipeline (both entry points): strip derived fields → resolve source type →
compute expiry → score → bucket → ``SourceClaim.model_validate`` → dedup by
``claim_id`` → store.

Corroboration / contradiction scoring counts **only references that already
resolve to a stored claim** — a fabricated or not-yet-ingested id earns no
bonus and incurs no penalty. This closes a gaming vector (an upstream producer
cannot inflate its own confidence with phantom corroborators) at the cost of
order-sensitivity: a claim ingested before its corroborators will not yet be
credited for them. The stored claim retains the *full* provided id lists for
audit; only the *score* is restricted to resolved references. A registry-aware
re-score on later ingestion is future work.

Every outcome is typed — no raw exception crosses this boundary (axiom 16).
"""

from __future__ import annotations

import threading
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from pydantic import ValidationError

from agentic_calendar.common.clock import Clock
from agentic_calendar.common.errors import AgenticCalendarError
from agentic_calendar.contracts.reason_codes import ReasonCode
from agentic_calendar.contracts.source_claim import (
    SourceClaim,
    SourceType,
    bucket_for_score,
)

from .classification import classify_source
from .expiration import compute_expires_at
from .priors import DEFAULT_CONFIDENCE_PRIORS, ConfidencePriors
from .scoring import score_confidence

#: Derived fields the kernel always computes; stripped from raw input so an
#: upstream producer (LLM, scraper) can never set them.
_DERIVED_FIELDS: frozenset[str] = frozenset(
    {"source_type", "confidence_score", "confidence_bucket", "expires_at"}
)


class SourceClaimStoreError(AgenticCalendarError):
    """Base for source-claim-store errors."""


class SourceClaimAlreadyExistsError(SourceClaimStoreError):
    """Attempted to append a ``claim_id`` that already exists."""


@runtime_checkable
class SourceClaimStore(Protocol):
    """Append/read surface for source claims."""

    def append(self, claim: SourceClaim) -> None: ...

    def exists(self, claim_id: str) -> bool: ...

    def get(self, claim_id: str) -> SourceClaim | None: ...

    def all(self) -> list[SourceClaim]: ...


class InMemorySourceClaimStore:
    """Default Phase 5 store. Thread-safe, ephemeral, non-persistent."""

    def __init__(self) -> None:
        self._by_id: dict[str, SourceClaim] = {}
        self._order: list[str] = []
        self._lock = threading.RLock()

    def append(self, claim: SourceClaim) -> None:
        """Append ``claim``. Rejects a duplicate id (the ingestor dedups first)."""
        with self._lock:
            if claim.claim_id in self._by_id:
                raise SourceClaimAlreadyExistsError(claim.claim_id)
            self._by_id[claim.claim_id] = claim
            self._order.append(claim.claim_id)

    def exists(self, claim_id: str) -> bool:
        with self._lock:
            return claim_id in self._by_id

    def get(self, claim_id: str) -> SourceClaim | None:
        with self._lock:
            return self._by_id.get(claim_id)

    def all(self) -> list[SourceClaim]:
        with self._lock:
            return [self._by_id[i] for i in self._order]


class ClaimIngestionStatus(StrEnum):
    """Outcome of one ingestion attempt."""

    INGESTED = "ingested"
    DUPLICATE = "duplicate"
    REJECTED = "rejected"


@dataclass(frozen=True)
class ClaimIngestionOutcome:
    """Result of an ingestion call.

    ``claim`` is the stored claim on ``INGESTED``, the pre-existing claim on
    ``DUPLICATE``, and ``None`` on ``REJECTED``. ``reason_code`` is set only on
    ``REJECTED``.
    """

    status: ClaimIngestionStatus
    claim: SourceClaim | None
    reason_code: ReasonCode | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.status is ClaimIngestionStatus.INGESTED


@dataclass(frozen=True)
class _Prepared:
    """Validated raw input shared by both ingestion entry points."""

    data: dict[str, Any]
    source_url: str
    published: date | None
    date_collected: date


def _as_date(value: Any) -> date | None:
    """Coerce a raw date value to ``date``; ``None`` stays ``None``."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise TypeError(f"expected an ISO date string or date, got {type(value).__name__}")


class SourceClaimIngestor:
    """Deterministically classify, score, expire, dedup, and store claims."""

    def __init__(
        self,
        *,
        clock: Clock,
        store: SourceClaimStore,
        priors: ConfidencePriors = DEFAULT_CONFIDENCE_PRIORS,
        known_company_domains: frozenset[str] = frozenset(),
        engineering_blog_hosts: frozenset[str] = frozenset(),
    ) -> None:
        self._clock = clock
        self._store = store
        self._priors = priors
        self._known_company_domains = known_company_domains
        self._engineering_blog_hosts = engineering_blog_hosts

    def ingest(self, raw: Mapping[str, Any]) -> ClaimIngestionOutcome:
        """Ingest one raw retrieved claim record (source type from URL)."""
        prepared = self._prepare(raw)
        if isinstance(prepared, ClaimIngestionOutcome):
            return prepared
        source_type = classify_source(
            prepared.source_url,
            known_company_domains=self._known_company_domains,
            engineering_blog_hosts=self._engineering_blog_hosts,
        )
        return self._finish(prepared, source_type)

    def ingest_curated(
        self, raw: Mapping[str, Any], *, source_type: SourceType
    ) -> ClaimIngestionOutcome:
        """Ingest internally-curated content with a known, trusted source type.

        The caller declares provenance (e.g. ``CANONICAL_TOPIC_MODULE``); the
        confidence score, bucket, and expiry are still computed deterministically
        — the caller never assigns confidence. Intended for an internal curation
        pipeline, not for untrusted retrieved/LLM-produced content.
        """
        prepared = self._prepare(raw)
        if isinstance(prepared, ClaimIngestionOutcome):
            return prepared
        return self._finish(prepared, source_type)

    def _prepare(self, raw: Mapping[str, Any]) -> _Prepared | ClaimIngestionOutcome:
        """Strip derived fields, validate source_url + dates. Typed rejection."""
        data = {k: v for k, v in raw.items() if k not in _DERIVED_FIELDS}

        source_url = data.get("source_url")
        if not isinstance(source_url, str) or not source_url:
            return _rejected("source_url is required and must be a non-empty string")

        try:
            date_collected = _as_date(data.get("date_collected"))
            published = _as_date(data.get("source_published_date"))
        except (ValueError, TypeError) as exc:
            return _rejected(f"invalid date: {exc}")
        if date_collected is None:
            return _rejected("date_collected is required")

        return _Prepared(
            data=data,
            source_url=source_url,
            published=published,
            date_collected=date_collected,
        )

    def _finish(
        self, prepared: _Prepared, source_type: SourceType
    ) -> ClaimIngestionOutcome:
        now = self._clock.now()
        anchor = prepared.published or prepared.date_collected
        expires_at = compute_expires_at(
            source_type, anchor=anchor, priors=self._priors
        )
        # Score credits only references that already resolve to a stored claim.
        corroborating = self._resolved_ids(prepared.data.get("corroborating_claim_ids"))
        contradicting = self._resolved_ids(prepared.data.get("contradicting_claim_ids"))
        score = score_confidence(
            source_type=source_type,
            source_published_date=prepared.published,
            expires_at=expires_at,
            corroborating_claim_ids=corroborating,
            contradicting_claim_ids=contradicting,
            now=now,
            priors=self._priors,
        )
        bucket = bucket_for_score(score)

        assembled = {
            **prepared.data,  # retains the full provided id lists for audit
            "source_type": source_type.value,
            "confidence_score": score,
            "confidence_bucket": bucket.value,
            "expires_at": expires_at.isoformat(),
        }

        try:
            claim = SourceClaim.model_validate(assembled)
        except ValidationError as exc:
            return ClaimIngestionOutcome(
                status=ClaimIngestionStatus.REJECTED,
                claim=None,
                reason_code=ReasonCode.SCHEMA_INVALID,
                error=str(exc),
            )

        existing = self._store.get(claim.claim_id)
        if existing is not None:
            return ClaimIngestionOutcome(
                status=ClaimIngestionStatus.DUPLICATE, claim=existing
            )

        self._store.append(claim)
        return ClaimIngestionOutcome(status=ClaimIngestionStatus.INGESTED, claim=claim)

    def _resolved_ids(self, value: Any) -> list[str]:
        """Distinct, store-resolved string ids from a raw reference list.

        A non-list, or ids that are not strings or not present in the store, are
        dropped — so phantom references never affect the score. The original
        (unfiltered) list is preserved on the stored claim via the assembled
        payload; only scoring uses this resolved view.
        """
        if not isinstance(value, list):
            return []
        resolved: dict[str, None] = {}
        for cid in value:
            if isinstance(cid, str) and cid not in resolved and self._store.exists(cid):
                resolved[cid] = None
        return list(resolved)


def _rejected(error: str) -> ClaimIngestionOutcome:
    return ClaimIngestionOutcome(
        status=ClaimIngestionStatus.REJECTED,
        claim=None,
        reason_code=ReasonCode.SCHEMA_INVALID,
        error=error,
    )
