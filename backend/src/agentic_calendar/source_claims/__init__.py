"""Source-claims kernel (Phase 5, axiom 08).

Deterministic ingestion of retrieved evidence into auditable
:class:`~agentic_calendar.contracts.source_claim.SourceClaim` objects:
domain/URL classification, the confidence formula, per-source expiry, and a
typed-outcome ingestor that is the only sanctioned producer of a claim's
score/bucket/expiry. An LLM may *explain* a claim but must never assign its
confidence; every magnitude here is an uncalibrated heuristic prior
(``priors.py``).

Leaf kernel: depends only on ``common`` and ``contracts``. Any region may import
it; nothing here reaches back into a region.
"""

from .classification import classify_source
from .curation import (
    DEFAULT_CLAIM_CURATION_CONFIG,
    ClaimCurationConfig,
    ClaimCurationResult,
    curate_claims,
)
from .expiration import compute_expires_at, is_expired
from .ingestion import (
    ClaimIngestionOutcome,
    ClaimIngestionStatus,
    InMemorySourceClaimStore,
    SourceClaimAlreadyExistsError,
    SourceClaimIngestor,
    SourceClaimStore,
    SourceClaimStoreError,
)
from .priors import DEFAULT_CONFIDENCE_PRIORS, ConfidencePriors
from .scoring import score_confidence

__all__ = [
    "DEFAULT_CLAIM_CURATION_CONFIG",
    "DEFAULT_CONFIDENCE_PRIORS",
    "ClaimCurationConfig",
    "ClaimCurationResult",
    "ClaimIngestionOutcome",
    "ClaimIngestionStatus",
    "ConfidencePriors",
    "InMemorySourceClaimStore",
    "SourceClaimAlreadyExistsError",
    "SourceClaimIngestor",
    "SourceClaimStore",
    "SourceClaimStoreError",
    "classify_source",
    "compute_expires_at",
    "curate_claims",
    "is_expired",
    "score_confidence",
]
