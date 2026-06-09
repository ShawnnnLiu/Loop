"""Tests for evidence-following cache invalidation (axiom 18)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from agentic_calendar.cache.invalidation import is_claim_live, is_entry_valid
from agentic_calendar.cache.keys import CacheKey, CacheTarget
from agentic_calendar.cache.store import CacheEntry
from agentic_calendar.contracts.source_claim import (
    ConfidenceBucket,
    SourceClaim,
    SourceType,
)

NOW = datetime(2026, 6, 4, 12, 0, tzinfo=UTC)


def _claim(
    claim_id: str, expires: date, *, contradicting: tuple[str, ...] = ()
) -> SourceClaim:
    return SourceClaim(
        claim_id=claim_id,
        claim_text="A verifiable claim.",
        source_url="https://x.example.com/a",
        source_type=SourceType.INTERVIEW_REPORT,
        date_collected=date(2026, 1, 1),
        confidence_score=0.6,
        confidence_bucket=ConfidenceBucket.MEDIUM,
        expires_at=expires,
        contradicting_claim_ids=list(contradicting),
    )


class _Registry:
    def __init__(self, claims: list[SourceClaim]) -> None:
        self._by_id = {c.claim_id: c for c in claims}

    def get(self, claim_id: str) -> SourceClaim | None:
        return self._by_id.get(claim_id)


def _entry(claims: tuple[str, ...], **key_overrides: Any) -> CacheEntry:
    base: dict[str, Any] = {
        "target": CacheTarget.SYLLABUS_UNITS,
        "role_target": "backend swe",
        "freshness_window": "2026-06",
        "object_schema_version": "syl-v1",
    }
    base.update(key_overrides)
    return CacheEntry(
        key=CacheKey(**base),
        value_kind=CacheTarget.SYLLABUS_UNITS,
        value_json={},
        source_claim_ids=claims,
        created_at=NOW,
    )


def test_live_claim() -> None:
    reg = _Registry([])
    assert is_claim_live(_claim("c1", date(2026, 12, 1)), now=NOW, registry=reg) is True


def test_expired_claim_not_live() -> None:
    reg = _Registry([])
    assert is_claim_live(_claim("c1", date(2026, 1, 1)), now=NOW, registry=reg) is False


def test_claim_with_live_contradictor_not_live() -> None:
    contra = _claim("c9", date(2026, 12, 1))  # present and unexpired
    claim = _claim("c1", date(2026, 12, 1), contradicting=("c9",))
    reg = _Registry([claim, contra])
    assert is_claim_live(claim, now=NOW, registry=reg) is False


def test_claim_with_phantom_contradictor_stays_live() -> None:
    # "c9" is not in the registry — a phantom/deleted contradictor no longer
    # poisons the claim, even though it is retained in contradicting_claim_ids.
    claim = _claim("c1", date(2026, 12, 1), contradicting=("c9",))
    reg = _Registry([claim])
    assert is_claim_live(claim, now=NOW, registry=reg) is True


def test_claim_with_expired_contradictor_stays_live() -> None:
    expired_contra = _claim("c9", date(2026, 1, 1))  # present but expired
    claim = _claim("c1", date(2026, 12, 1), contradicting=("c9",))
    reg = _Registry([claim, expired_contra])
    assert is_claim_live(claim, now=NOW, registry=reg) is True


def test_entry_valid_when_all_claims_live() -> None:
    reg = _Registry([_claim("c1", date(2026, 12, 1))])
    assert is_entry_valid(_entry(("c1",)), now=NOW, registry=reg) is True


def test_entry_invalid_when_claim_missing() -> None:
    reg = _Registry([])
    assert is_entry_valid(_entry(("missing",)), now=NOW, registry=reg) is False


def test_entry_invalid_when_claim_contradicted() -> None:
    # The contradictor must itself be live for the entry to be treated as stale.
    reg = _Registry(
        [
            _claim("c1", date(2026, 12, 1), contradicting=("c9",)),
            _claim("c9", date(2026, 12, 1)),
        ]
    )
    assert is_entry_valid(_entry(("c1",)), now=NOW, registry=reg) is False


def test_entry_stays_valid_when_contradictor_expired() -> None:
    # Contradictor present but expired → no longer blocks the entry.
    reg = _Registry(
        [
            _claim("c1", date(2026, 12, 1), contradicting=("c9",)),
            _claim("c9", date(2026, 1, 1)),
        ]
    )
    assert is_entry_valid(_entry(("c1",)), now=NOW, registry=reg) is True


def test_empty_refs_entry_is_trivially_valid() -> None:
    assert is_entry_valid(_entry(()), now=NOW, registry=_Registry([])) is True


def test_entry_goes_stale_after_claim_expiry() -> None:
    claim = _claim("c1", date(2026, 6, 10))
    reg = _Registry([claim])
    entry = _entry(("c1",))
    assert is_entry_valid(entry, now=NOW, registry=reg) is True
    at_expiry = datetime(2026, 6, 10, 12, 0, tzinfo=UTC)  # inclusive boundary
    assert is_entry_valid(entry, now=at_expiry, registry=reg) is False
