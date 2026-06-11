"""Shared builders for consent-region tests."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from agentic_calendar.contracts.consent_record import (
    ConsentRecord,
    ConsentScope,
    ConsentStatus,
)

T0 = datetime(2026, 6, 10, 16, 0, 0, tzinfo=UTC)
"""Frozen 'now' used across consent tests."""


def build_consent_record(**overrides: Any) -> ConsentRecord:
    """A valid granted pooled-training record; override any field."""
    payload: dict[str, Any] = {
        "consent_record_id": "consent_001",
        "user_id": "user_123",
        "scope": ConsentScope.POOLED_TRAINING,
        "status": ConsentStatus.GRANTED,
        "consent_version": "2026-06",
        "granted_at": T0,
        "revoked_at": None,
        "created_at": T0,
        "updated_at": T0,
    }
    payload.update(overrides)
    return ConsentRecord.model_validate(payload)
