"""Tests for ``DataAccessAuditEntry``."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from agentic_calendar.contracts.data_access_audit import (
    DATA_CONTROL_PURPOSES,
    DataAccessAuditEntry,
    DataAccessPurpose,
)
from tests._fixture_loader import iter_invalid, iter_valid

CONTRACT = "data_access_audit"


@pytest.mark.parametrize(
    "fixture",
    list(iter_valid(CONTRACT)),
    ids=lambda f: f.name,
)
def test_valid_fixture_parses(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    entry = DataAccessAuditEntry.model_validate(payload)
    assert entry.audit_entry_id == payload["audit_entry_id"]


@pytest.mark.parametrize(
    "fixture",
    list(iter_invalid(CONTRACT)),
    ids=lambda f: f.name,
)
def test_invalid_fixture_rejected(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    expected = fixture.expected  # type: ignore[attr-defined]
    with pytest.raises(ValidationError) as exc_info:
        DataAccessAuditEntry.model_validate(payload)
    msg = str(exc_info.value)
    for substr in expected["error_substrings"]:
        assert substr in msg, (
            f"expected substring {substr!r} not in error message:\n{msg}"
        )


def test_reason_code_defaults_to_null() -> None:
    """A minimal allowed gate entry parses without an explicit reason_code."""
    minimal = {
        "audit_entry_id": "audit_min_001",
        "user_id": "user_123",
        "purpose": "cohort_retrieval",
        "accessor": "retrieval_pipeline",
        "outcome": "allowed",
        "created_at": "2026-06-10T09:30:00-07:00",
    }
    entry = DataAccessAuditEntry.model_validate(minimal)
    assert entry.reason_code is None


def test_data_control_purposes_set_matches_spec() -> None:
    expected = {
        DataAccessPurpose.DATA_VIEW,
        DataAccessPurpose.DATA_EXPORT,
        DataAccessPurpose.DATA_DELETE,
    }
    assert expected == DATA_CONTROL_PURPOSES
