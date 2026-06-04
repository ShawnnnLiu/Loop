"""Tests for ``Sponsor``."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from agentic_calendar.contracts.sponsor import Sponsor
from tests._fixture_loader import iter_invalid, iter_valid

CONTRACT = "sponsor"


@pytest.mark.parametrize(
    "fixture",
    list(iter_valid(CONTRACT)),
    ids=lambda f: f.name,
)
def test_valid_fixture_parses(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    s = Sponsor.model_validate(payload)
    assert s.sponsor_id == payload["sponsor_id"]


@pytest.mark.parametrize(
    "fixture",
    list(iter_invalid(CONTRACT)),
    ids=lambda f: f.name,
)
def test_invalid_fixture_rejected(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    expected = fixture.expected  # type: ignore[attr-defined]
    with pytest.raises(ValidationError) as exc_info:
        Sponsor.model_validate(payload)
    msg = str(exc_info.value)
    for substr in expected["error_substrings"]:
        assert substr in msg, (
            f"expected substring {substr!r} not in error message:\n{msg}"
        )


def test_is_reportable_accepted_vs_revoked() -> None:
    accepted = Sponsor.model_validate(
        {
            "sponsor_id": "spn_r1",
            "user_id": "user_r",
            "relationship": "mentor",
            "contact_channel": "in_app",
            "status": "accepted",
            "invited_at": "2026-04-20T09:00:00+00:00",
            "accepted_at": "2026-04-21T10:00:00+00:00",
            "revoked_at": None,
            "created_at": "2026-04-20T09:00:00+00:00",
            "updated_at": "2026-04-21T10:00:00+00:00",
        }
    )
    assert accepted.is_reportable() is True

    revoked = Sponsor.model_validate(
        {
            "sponsor_id": "spn_r2",
            "user_id": "user_r",
            "relationship": "coach",
            "contact_channel": "email",
            "status": "revoked",
            "invited_at": "2026-04-20T09:00:00+00:00",
            "accepted_at": "2026-04-21T10:00:00+00:00",
            "revoked_at": "2026-04-30T12:00:00+00:00",
            "created_at": "2026-04-20T09:00:00+00:00",
            "updated_at": "2026-04-30T12:00:00+00:00",
        }
    )
    assert revoked.is_reportable() is False

    pending = Sponsor.model_validate(
        {
            "sponsor_id": "spn_r3",
            "user_id": "user_r",
            "relationship": "parent",
            "contact_channel": "push",
            "status": "pending",
            "invited_at": "2026-04-20T09:00:00+00:00",
            "accepted_at": None,
            "revoked_at": None,
            "created_at": "2026-04-20T09:00:00+00:00",
            "updated_at": "2026-04-20T09:00:00+00:00",
        }
    )
    assert pending.is_reportable() is False
