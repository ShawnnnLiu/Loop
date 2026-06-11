"""Tests for cache keys (axiom 18)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from agentic_calendar.cache.keys import (
    CacheKey,
    CacheTarget,
    company_target_key,
    make_claim_version_set,
    month_bucket,
)
from tests._fixture_loader import iter_invalid, iter_valid


def _key(**overrides: Any) -> CacheKey:
    base: dict[str, Any] = {
        "target": CacheTarget.SYLLABUS_UNITS,
        "role_target": "Backend SWE",
        "company_target": "stripe",
        "freshness_window": "2026-06",
        "claim_version_set": ("a", "b"),
        "object_schema_version": "syl-v1",
    }
    base.update(overrides)
    return CacheKey(**base)


def test_make_claim_version_set_sorted_distinct() -> None:
    assert make_claim_version_set(["b", "a", "a", ""]) == ("a", "b")


def test_order_and_casing_collide() -> None:
    k1 = _key(role_target="Backend SWE", claim_version_set=["b", "a", "a"])
    k2 = _key(role_target="backend swe", claim_version_set=["a", "b"])
    assert k1.fingerprint() == k2.fingerprint()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("object_schema_version", "syl-v2"),
        ("cache_schema_version", "cache-key-v3"),
        ("cohort_id", "intermediate|backend swe"),
        ("role_target", "frontend swe"),
        ("company_target", "meta"),
        ("freshness_window", "2026-07"),
        ("claim_version_set", ("a", "b", "c")),
        ("target", CacheTarget.RAG_RETRIEVAL),
    ],
)
def test_each_dimension_changes_fingerprint(field: str, value: Any) -> None:
    assert _key().fingerprint() != _key(**{field: value}).fingerprint()


def test_empty_claim_set_is_stable() -> None:
    assert _key(claim_version_set=[]).fingerprint() == _key(
        claim_version_set=()
    ).fingerprint()


def test_month_bucket_boundary() -> None:
    assert month_bucket(datetime(2026, 6, 4, tzinfo=UTC)) == "2026-06"
    end_of_may = month_bucket(datetime(2026, 5, 31, 23, 59, tzinfo=UTC))
    start_of_june = month_bucket(datetime(2026, 6, 1, 0, 0, tzinfo=UTC))
    assert end_of_may != start_of_june


def test_company_target_key_order_insensitive() -> None:
    assert company_target_key(["Meta", "stripe"]) == company_target_key(
        ["stripe", "META"]
    )


CONTRACT = "cache_key"


@pytest.mark.parametrize("fixture", list(iter_valid(CONTRACT)), ids=lambda f: f.name)
def test_valid_fixture_parses(fixture: object) -> None:
    obj = CacheKey.model_validate(fixture.payload)  # type: ignore[attr-defined]
    assert isinstance(obj, CacheKey)


@pytest.mark.parametrize("fixture", list(iter_invalid(CONTRACT)), ids=lambda f: f.name)
def test_invalid_fixture_rejected(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    expected = fixture.expected  # type: ignore[attr-defined]
    with pytest.raises(ValidationError) as exc_info:
        CacheKey.model_validate(payload)
    msg = str(exc_info.value)
    for substr in expected["error_substrings"]:
        assert substr in msg, f"expected substring {substr!r} not in:\n{msg}"
