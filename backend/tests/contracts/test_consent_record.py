"""Tests for ``ConsentRecord``."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from agentic_calendar.contracts.consent_record import (
    ALLOWED_CONSENT_TRANSITIONS,
    ConsentRecord,
    ConsentStatus,
    is_allowed_consent_transition,
)
from tests._fixture_loader import iter_invalid, iter_valid

CONTRACT = "consent_record"


@pytest.mark.parametrize(
    "fixture",
    list(iter_valid(CONTRACT)),
    ids=lambda f: f.name,
)
def test_valid_fixture_parses(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    record = ConsentRecord.model_validate(payload)
    assert record.consent_record_id == payload["consent_record_id"]


@pytest.mark.parametrize(
    "fixture",
    list(iter_invalid(CONTRACT)),
    ids=lambda f: f.name,
)
def test_invalid_fixture_rejected(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    expected = fixture.expected  # type: ignore[attr-defined]
    with pytest.raises(ValidationError) as exc_info:
        ConsentRecord.model_validate(payload)
    msg = str(exc_info.value)
    for substr in expected["error_substrings"]:
        assert substr in msg, (
            f"expected substring {substr!r} not in error message:\n{msg}"
        )


def test_transition_matrix_revoked_is_terminal() -> None:
    """The only legal transition is granted → revoked (spec "Lifecycle")."""
    assert is_allowed_consent_transition(ConsentStatus.GRANTED, ConsentStatus.REVOKED)
    assert not is_allowed_consent_transition(ConsentStatus.REVOKED, ConsentStatus.GRANTED)
    assert not is_allowed_consent_transition(ConsentStatus.REVOKED, ConsentStatus.REVOKED)
    assert not is_allowed_consent_transition(ConsentStatus.GRANTED, ConsentStatus.GRANTED)
    assert ALLOWED_CONSENT_TRANSITIONS[ConsentStatus.REVOKED] == frozenset()


def test_is_active_tracks_status() -> None:
    granted = ConsentRecord.model_validate(
        {
            "consent_record_id": "consent_a",
            "user_id": "user_123",
            "scope": "pooled_training",
            "status": "granted",
            "consent_version": "2026-06",
            "granted_at": "2026-06-10T09:00:00-07:00",
            "created_at": "2026-06-10T09:00:00-07:00",
            "updated_at": "2026-06-10T09:00:00-07:00",
        }
    )
    assert granted.is_active() is True
    revoked = ConsentRecord.model_validate(
        granted.model_dump()
        | {
            "status": "revoked",
            "revoked_at": "2026-06-11T09:00:00-07:00",
            "updated_at": "2026-06-11T09:00:00-07:00",
        }
    )
    assert revoked.is_active() is False


def test_record_is_frozen() -> None:
    record = ConsentRecord.model_validate(
        {
            "consent_record_id": "consent_b",
            "user_id": "user_123",
            "scope": "cohort_retrieval",
            "status": "granted",
            "consent_version": "2026-06",
            "granted_at": "2026-06-10T09:00:00-07:00",
            "created_at": "2026-06-10T09:00:00-07:00",
            "updated_at": "2026-06-10T09:00:00-07:00",
        }
    )
    with pytest.raises(ValidationError):
        record.status = ConsentStatus.REVOKED  # type: ignore[misc]
