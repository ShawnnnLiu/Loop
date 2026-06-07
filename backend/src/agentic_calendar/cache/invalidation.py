"""Cache invalidation that follows the evidence (axiom 18).

A cache entry is only as live as the source claims that justify it. An entry is
stale when any referenced claim is missing from the registry, expired, or
contradicted — so the composition root treats a stale hit as a miss and
regenerates. ``now`` always comes from the injected ``Clock``, never wall-clock.

The ``ClaimRegistry`` protocol is structural: the source-claims store satisfies
it without this region importing that kernel (cache depends only on ``contracts``
+ ``common``).
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from agentic_calendar.contracts.source_claim import SourceClaim

from .store import CacheEntry


@runtime_checkable
class ClaimRegistry(Protocol):
    """Read-only lookup over source claims (satisfied by the claim store)."""

    def get(self, claim_id: str) -> SourceClaim | None: ...


def is_claim_live(claim: SourceClaim, now: datetime) -> bool:
    """A claim is live when it is neither expired nor contradicted."""
    if claim.is_expired(now):
        return False
    return not claim.contradicting_claim_ids


def is_entry_valid(
    entry: CacheEntry, *, now: datetime, registry: ClaimRegistry
) -> bool:
    """True when every claim justifying ``entry`` is present and live.

    An entry with no justifying claims is trivially valid.
    """
    for claim_id in entry.source_claim_ids:
        claim = registry.get(claim_id)
        if claim is None or not is_claim_live(claim, now):
            return False
    return True
