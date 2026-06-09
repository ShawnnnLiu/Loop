"""Cache invalidation that follows the evidence (axiom 18).

A cache entry is only as live as the source claims that justify it. An entry is
stale when any referenced claim is missing from the registry, expired, or
actively contradicted (contradicted by a claim that is itself still present and
unexpired) — so the composition root treats a stale hit as a miss and
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


def is_claim_live(
    claim: SourceClaim, *, now: datetime, registry: ClaimRegistry
) -> bool:
    """A claim is live when it is neither expired nor *actively* contradicted.

    A contradiction counts only while the contradicting claim is itself live
    evidence — present in ``registry`` and not yet expired. A contradictor that
    has been removed from the store, or has itself expired, no longer blocks this
    claim. This is evidence-following (axiom 18) and symmetric with ingestion,
    which only credits corroborators that resolve to a stored claim: a phantom or
    stale contradictor must not poison an entry forever, because
    ``contradicting_claim_ids`` is retained in full for audit and never pruned.

    The contradictor is checked one level deep (present + not expired); we do not
    recurse into whether the contradictor is itself contradicted. That avoids
    mutual-contradiction cycles and keeps invalidation conservative: any live
    contradiction on record forces the composition root to regenerate.
    """
    if claim.is_expired(now):
        return False
    for contra_id in claim.contradicting_claim_ids:
        contra = registry.get(contra_id)
        if contra is not None and not contra.is_expired(now):
            return False
    return True


def is_entry_valid(
    entry: CacheEntry, *, now: datetime, registry: ClaimRegistry
) -> bool:
    """True when every claim justifying ``entry`` is present and live.

    An entry with no justifying claims is trivially valid.
    """
    for claim_id in entry.source_claim_ids:
        claim = registry.get(claim_id)
        if claim is None or not is_claim_live(claim, now=now, registry=registry):
            return False
    return True
