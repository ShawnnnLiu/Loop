"""Cache region (Phase 5, axiom 18).

Deterministic, byte-stable cache keys over stable units of work, an in-memory
store that overwrites on ``put``, and invalidation that follows source-claim
expiration/contradiction. A cache hit short-circuits expensive Strategist work
for stable role/company targets; a stale hit (expired/contradicted evidence) is
treated as a miss by the composition root.

Leaf region: depends only on ``common`` and ``contracts``. The composition root
(operator CLIs / future app layer) wires it to the claim store and Strategist.
"""

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
    "InMemoryCache",
    "company_target_key",
    "is_claim_live",
    "is_entry_valid",
    "make_claim_version_set",
    "month_bucket",
]
