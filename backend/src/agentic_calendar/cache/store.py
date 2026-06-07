"""In-memory cache store (Phase 5, axiom 18).

Unlike the append-only telemetry/source-claim stores, a cache **overwrites** on
``put`` and supports deletion (``invalidate`` / ``invalidate_claim``). Each entry
records the ``source_claim_ids`` that justify it so invalidation can follow claim
expiration/contradiction (see ``invalidation.py``). MVP-only: in-memory, no
persistence, no Redis.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, model_validator

from .errors import CacheError
from .keys import CacheKey, CacheTarget


class CacheEntry(BaseModel):
    """One cached value plus the evidence that justifies it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    key: CacheKey
    value_kind: CacheTarget
    value_json: dict[str, Any]
    source_claim_ids: tuple[str, ...] = ()
    created_at: datetime

    @model_validator(mode="after")
    def _consistent(self) -> CacheEntry:
        if self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        if self.value_kind is not self.key.target:
            raise ValueError(
                f"value_kind {self.value_kind.value!r} must match "
                f"key.target {self.key.target.value!r}"
            )
        return self


@runtime_checkable
class Cache(Protocol):
    """Read/write surface for the cache."""

    def get(self, key: CacheKey) -> CacheEntry | None: ...

    def put(self, entry: CacheEntry) -> None: ...

    def invalidate(self, key: CacheKey) -> bool: ...

    def invalidate_claim(self, claim_id: str) -> list[CacheKey]: ...

    def all(self) -> list[CacheEntry]: ...


class InMemoryCache:
    """Default Phase 5 cache. Thread-safe, ephemeral, overwrite-on-put."""

    def __init__(self) -> None:
        self._by_fp: dict[str, CacheEntry] = {}
        self._order: list[str] = []
        self._lock = threading.RLock()

    def get(self, key: CacheKey) -> CacheEntry | None:
        with self._lock:
            return self._by_fp.get(key.fingerprint())

    def put(self, entry: CacheEntry) -> None:
        """Insert or overwrite the entry for its key's fingerprint.

        Raises ``CacheError`` if ``value_json`` is not JSON-serializable — the
        cache only stores values that can be persisted and audited (the field is
        ``value_json`` by contract), so a non-serializable value is rejected at
        write time rather than failing later at dump/inspect time.
        """
        try:
            json.dumps(entry.value_json)
        except (TypeError, ValueError) as exc:
            raise CacheError(
                f"cache value_json is not JSON-serializable: {exc}"
            ) from exc
        fingerprint = entry.key.fingerprint()
        with self._lock:
            if fingerprint not in self._by_fp:
                self._order.append(fingerprint)
            self._by_fp[fingerprint] = entry

    def invalidate(self, key: CacheKey) -> bool:
        """Drop the entry for ``key``. Returns True if one was present."""
        fingerprint = key.fingerprint()
        with self._lock:
            if fingerprint in self._by_fp:
                del self._by_fp[fingerprint]
                self._order.remove(fingerprint)
                return True
            return False

    def invalidate_claim(self, claim_id: str) -> list[CacheKey]:
        """Drop every entry justified by ``claim_id``. Returns the dropped keys."""
        with self._lock:
            dropped: list[CacheKey] = []
            for fingerprint in list(self._order):
                entry = self._by_fp[fingerprint]
                if claim_id in entry.source_claim_ids:
                    dropped.append(entry.key)
                    del self._by_fp[fingerprint]
                    self._order.remove(fingerprint)
            return dropped

    def all(self) -> list[CacheEntry]:
        with self._lock:
            return [self._by_fp[fp] for fp in self._order]
