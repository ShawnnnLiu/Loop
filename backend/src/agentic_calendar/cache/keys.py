"""Cache keys for stable, reusable units of work (axiom 18).

Cache only stable units (company interview patterns, topic modules, RAG
retrieval results, task templates, syllabi) — never full per-user plans. A key's
dimensions are exactly axiom 18's: role target, company target, freshness
window, the source-claim version set, and the *schema version of the cached
object* (so a contract change forces regeneration). The key also carries its own
``cache_schema_version`` so a key-format change invalidates everything.

Keys are byte-stable: the claim set is sorted and de-duplicated and string
dimensions are normalised, so two requests that differ only in claim order or
casing collide to the same fingerprint.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from agentic_calendar.contracts.hashing import canonical_mapping_hash

#: Version of the cache-key format itself. Bump to invalidate every key.
CACHE_SCHEMA_VERSION = "cache-key-v1"


class CacheTarget(StrEnum):
    """The kinds of stable unit the cache stores (axiom 18)."""

    COMPANY_INTERVIEW_PATTERN = "company_interview_pattern"
    TOPIC_MODULE = "topic_module"
    RAG_RETRIEVAL = "rag_retrieval"
    TASK_TEMPLATE = "task_template"
    SKILL_TO_CURRICULUM = "skill_to_curriculum"
    SYLLABUS_UNITS = "syllabus_units"


def make_claim_version_set(claim_ids: Iterable[str]) -> tuple[str, ...]:
    """Sorted, de-duplicated claim-id tuple — order/multiplicity-insensitive."""
    return tuple(sorted({c for c in claim_ids if c}))


def company_target_key(names: Iterable[str]) -> str:
    """Normalised, order-insensitive company-target dimension from company names."""
    return "|".join(sorted({n.strip().casefold() for n in names if n.strip()}))


def month_bucket(now: datetime) -> str:
    """Freshness window as a ``YYYY-MM`` bucket, derived from the injected clock."""
    return f"{now.year:04d}-{now.month:02d}"


class CacheKey(BaseModel):
    """Auditable, byte-stable cache key (axiom 18 dimensions)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    target: CacheTarget
    role_target: str = Field(min_length=1)
    company_target: str = ""
    freshness_window: str = Field(min_length=1)
    claim_version_set: tuple[str, ...] = ()
    object_schema_version: str = Field(min_length=1)
    cache_schema_version: str = CACHE_SCHEMA_VERSION

    @model_validator(mode="before")
    @classmethod
    def _normalize(cls, data: Any) -> Any:
        if isinstance(data, dict):
            data = dict(data)
            for field in ("role_target", "company_target"):
                value = data.get(field)
                if isinstance(value, str):
                    data[field] = value.strip().casefold()
            cvs = data.get("claim_version_set")
            if cvs is not None:
                data["claim_version_set"] = make_claim_version_set(cvs)
        return data

    def fingerprint(self) -> str:
        """Stable ``"sha256:<hex>"`` identity for this key (storage lookup)."""
        return canonical_mapping_hash(self.model_dump(mode="json"))
