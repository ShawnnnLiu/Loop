"""Cache region (Phase 5, axiom 18).

Deterministic, byte-stable cache keys over stable units of work, an in-memory
store that overwrites on ``put``, and invalidation that follows source-claim
expiration/contradiction.

**Status: realized but unwired.** This kernel is complete and tested, but no
production composition root constructs a ``Cache`` — ``AppEnvironment`` does not
carry one, and the Strategist path never consults it. Only the operator CLIs
(``tools/inspect_cache.py``, ``tools/export_schemas.py``) touch it. It awaits
the RAG phase, whose retrieval results are the cache targets axiom 18 was
written for; wiring a syllabus-reuse short-circuit earlier would trade syllabus
freshness for a cost saving the current cost posture does not need. Until then,
the only caching in production is provider-side prompt caching inside the
Anthropic transport (see ``llm_nodes/anthropic_adapter.py``).

Leaf region: depends only on ``common`` and ``contracts``. The composition root
(operator CLIs / future app layer) wires it to the claim store and Strategist.
"""

from .cohort import (
    CohortLookupResult,
    CohortLookupSource,
    cohort_lookup,
    cohort_scoped_key,
    derive_cohort_id,
)
from .errors import CacheError
from .invalidation import ClaimRegistry, is_claim_live, is_entry_valid
from .keys import (
    CACHE_SCHEMA_VERSION,
    CacheKey,
    CacheTarget,
    company_target_key,
    make_claim_version_set,
    month_bucket,
)
from .store import Cache, CacheEntry, InMemoryCache

__all__ = [
    "CACHE_SCHEMA_VERSION",
    "Cache",
    "CacheEntry",
    "CacheError",
    "CacheKey",
    "CacheTarget",
    "ClaimRegistry",
    "CohortLookupResult",
    "CohortLookupSource",
    "InMemoryCache",
    "cohort_lookup",
    "cohort_scoped_key",
    "company_target_key",
    "derive_cohort_id",
    "is_claim_live",
    "is_entry_valid",
    "make_claim_version_set",
    "month_bucket",
]
