"""Tests for the in-memory cache store (axiom 18)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from agentic_calendar.cache.errors import CacheError
from agentic_calendar.cache.keys import CacheKey, CacheTarget
from agentic_calendar.cache.store import CacheEntry, InMemoryCache
from tests._fixture_loader import iter_invalid, iter_valid

NOW = datetime(2026, 6, 4, 12, 0, tzinfo=UTC)


def _key(**overrides: Any) -> CacheKey:
    base: dict[str, Any] = {
        "target": CacheTarget.SYLLABUS_UNITS,
        "role_target": "backend swe",
        "freshness_window": "2026-06",
        "object_schema_version": "syl-v1",
    }
    base.update(overrides)
    return CacheKey(**base)


def _entry(
    key: CacheKey,
    *,
    value: dict[str, Any] | None = None,
    claims: tuple[str, ...] = (),
) -> CacheEntry:
    return CacheEntry(
        key=key,
        value_kind=key.target,
        value_json=value if value is not None else {"v": 1},
        source_claim_ids=claims,
        created_at=NOW,
    )


def test_put_get_roundtrip() -> None:
    cache = InMemoryCache()
    key = _key()
    cache.put(_entry(key))
    got = cache.get(key)
    assert got is not None and got.value_json == {"v": 1}


def test_put_overwrites() -> None:
    cache = InMemoryCache()
    key = _key()
    cache.put(_entry(key, value={"v": 1}))
    cache.put(_entry(key, value={"v": 2}))
    assert len(cache.all()) == 1  # overwrite, not append (unlike telemetry)
    got = cache.get(key)
    assert got is not None and got.value_json == {"v": 2}


def test_invalidate() -> None:
    cache = InMemoryCache()
    key = _key()
    cache.put(_entry(key))
    assert cache.invalidate(key) is True
    assert cache.get(key) is None
    assert cache.invalidate(key) is False  # already gone


def test_invalidate_claim_drops_referencing_entries() -> None:
    cache = InMemoryCache()
    key_a = _key(claim_version_set=("c1",))
    key_b = _key(claim_version_set=("c2",))
    cache.put(_entry(key_a, claims=("c1", "shared")))
    cache.put(_entry(key_b, claims=("c2",)))
    dropped = cache.invalidate_claim("c1")
    assert len(dropped) == 1
    assert cache.get(key_a) is None
    assert cache.get(key_b) is not None  # untouched


def test_value_kind_must_match_key_target() -> None:
    key = _key(target=CacheTarget.SYLLABUS_UNITS)
    with pytest.raises(ValidationError):
        CacheEntry(
            key=key,
            value_kind=CacheTarget.RAG_RETRIEVAL,
            value_json={},
            created_at=NOW,
        )


def test_created_at_must_be_timezone_aware() -> None:
    with pytest.raises(ValidationError):
        CacheEntry(
            key=_key(),
            value_kind=CacheTarget.SYLLABUS_UNITS,
            value_json={},
            created_at=datetime(2026, 6, 4, 12, 0),  # naive
        )


def test_put_rejects_non_serializable_value() -> None:
    cache = InMemoryCache()
    entry = CacheEntry(
        key=_key(),
        value_kind=CacheTarget.SYLLABUS_UNITS,
        value_json={"bad": {1, 2}},  # a set is not JSON-serializable
        created_at=NOW,
    )
    with pytest.raises(CacheError):
        cache.put(entry)


CONTRACT = "cache_entry"


@pytest.mark.parametrize("fixture", list(iter_valid(CONTRACT)), ids=lambda f: f.name)
def test_valid_fixture_parses(fixture: object) -> None:
    obj = CacheEntry.model_validate(fixture.payload)  # type: ignore[attr-defined]
    assert isinstance(obj, CacheEntry)


@pytest.mark.parametrize("fixture", list(iter_invalid(CONTRACT)), ids=lambda f: f.name)
def test_invalid_fixture_rejected(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    expected = fixture.expected  # type: ignore[attr-defined]
    with pytest.raises(ValidationError) as exc_info:
        CacheEntry.model_validate(payload)
    msg = str(exc_info.value)
    for substr in expected["error_substrings"]:
        assert substr in msg, f"expected substring {substr!r} not in:\n{msg}"
