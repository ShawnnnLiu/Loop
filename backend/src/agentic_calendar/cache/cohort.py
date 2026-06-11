"""Consent-gated cohort retrieval over the Phase 5 cache (Phase 6d; ADR-0007).

Cohort assignment is deterministic — bucket by experience level and
normalised goal — and the cohort cache namespace is reachable **only**
behind the ``cohort_retrieval`` consent scope (consent-record spec). The
consent gate itself lives in ``consent/`` and is checked (and audited) by
the composition root; this kernel receives only the resulting cohort id, or
None when consent was missing/revoked, and cannot widen access on its own:
with ``cohort_id=None`` the lookup is byte-identical to the pre-Phase-6d
global path.

Source-claim invalidation and deterministic confidence scoring (axiom 08)
are unchanged — cohort entries carry ``source_claim_ids`` like any other.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from agentic_calendar.contracts.common_types import ExperienceLevel

from .keys import CacheKey
from .store import Cache, CacheEntry


def derive_cohort_id(experience_level: ExperienceLevel, role_target: str) -> str:
    """Deterministic cohort bucket: ``"<experience>|<normalised role>"``.

    Raises ``ValueError`` on an empty role — a cohort must name a goal.
    """
    role = role_target.strip().casefold()
    if not role:
        raise ValueError("role_target must be non-empty")
    return f"{experience_level.value}|{role}"


class CohortLookupSource(StrEnum):
    """Which namespace served a cohort-aware lookup (explainability)."""

    COHORT = "cohort"
    GLOBAL = "global"
    MISS = "miss"


@dataclass(frozen=True)
class CohortLookupResult:
    """Outcome of one cohort-aware cache lookup, naming the winner."""

    entry: CacheEntry | None
    source: CohortLookupSource


def cohort_scoped_key(key: CacheKey, cohort_id: str) -> CacheKey:
    """Return ``key`` re-scoped to the cohort namespace.

    Rebuilt through the model so normalization and every key invariant
    re-run (house rule: never ``model_copy`` past validators).
    """
    if not cohort_id.strip():
        raise ValueError("cohort_id must be non-empty; use the global key instead")
    return CacheKey.model_validate(key.model_dump() | {"cohort_id": cohort_id})


def cohort_lookup(
    cache: Cache,
    key: CacheKey,
    *,
    cohort_id: str | None,
) -> CohortLookupResult:
    """Look up ``key``, preferring the cohort namespace when consented.

    ``cohort_id`` must be None when the consent gate denied
    ``cohort_retrieval`` (or was never checked) — the lookup then touches
    only the global namespace, exactly the pre-Phase-6d behavior. ``key``
    itself must be a global key (empty ``cohort_id``); the cohort-scoped
    variant is derived here so the two namespaces cannot be mixed up.
    """
    if key.cohort_id:
        raise ValueError("pass the global key; cohort scoping happens inside the lookup")
    if cohort_id is not None:
        cohort_entry = cache.get(cohort_scoped_key(key, cohort_id))
        if cohort_entry is not None:
            return CohortLookupResult(entry=cohort_entry, source=CohortLookupSource.COHORT)
    global_entry = cache.get(key)
    if global_entry is not None:
        return CohortLookupResult(entry=global_entry, source=CohortLookupSource.GLOBAL)
    return CohortLookupResult(entry=None, source=CohortLookupSource.MISS)
