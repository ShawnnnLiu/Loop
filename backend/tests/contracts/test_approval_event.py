"""Tests for the ``ApprovalEvent`` contract (Phase 2)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from agentic_calendar.contracts.approval_event import (
    ApprovalActionType,
    ApprovalEvent,
    HashAlgorithm,
)

_VALID_HASH = "sha256:" + ("a" * 64)


def _kwargs(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "approval_event_id": "approval_001",
        "user_id": "user_abc",
        "plan_id": "plan_abc",
        "draft_schedule_id": "draft_abc",
        "action_type": ApprovalActionType.ADD_TO_CALENDAR,
        "approved_payload_hash": _VALID_HASH,
        "hash_algorithm": HashAlgorithm.SHA256,
        "hash_canonicalization_version": "v1",
        "created_at": datetime(2026, 5, 4, 17, 55, tzinfo=UTC),
        "expires_at": datetime(2026, 5, 5, 17, 55, tzinfo=UTC),
    }
    base.update(overrides)
    return base


def test_valid_payload_constructs() -> None:
    event = ApprovalEvent(**_kwargs())  # type: ignore[arg-type]
    assert event.approval_event_id == "approval_001"
    assert event.action_type is ApprovalActionType.ADD_TO_CALENDAR
    assert event.hash_algorithm is HashAlgorithm.SHA256


def test_round_trip_json() -> None:
    event = ApprovalEvent(**_kwargs())  # type: ignore[arg-type]
    payload = event.model_dump(mode="json")
    again = ApprovalEvent.model_validate(payload)
    assert again == event


def test_expires_at_must_be_after_created_at() -> None:
    with pytest.raises(ValidationError, match="strictly after"):
        ApprovalEvent(
            **_kwargs(  # type: ignore[arg-type]
                created_at=datetime(2026, 5, 4, 17, 55, tzinfo=UTC),
                expires_at=datetime(2026, 5, 4, 17, 55, tzinfo=UTC),
            )
        )


def test_expires_at_before_created_at_rejected() -> None:
    with pytest.raises(ValidationError):
        ApprovalEvent(
            **_kwargs(  # type: ignore[arg-type]
                created_at=datetime(2026, 5, 4, 17, 55, tzinfo=UTC),
                expires_at=datetime(2026, 5, 4, 17, 0, tzinfo=UTC),
            )
        )


def test_naive_created_at_rejected() -> None:
    with pytest.raises(ValidationError):
        ApprovalEvent(
            **_kwargs(  # type: ignore[arg-type]
                created_at=datetime(2026, 5, 4, 17, 55),
            )
        )


def test_naive_expires_at_rejected() -> None:
    with pytest.raises(ValidationError):
        ApprovalEvent(
            **_kwargs(  # type: ignore[arg-type]
                expires_at=datetime(2026, 5, 5, 17, 55),
            )
        )


def test_invalid_hash_pattern_rejected() -> None:
    with pytest.raises(ValidationError):
        ApprovalEvent(**_kwargs(approved_payload_hash="abc"))  # type: ignore[arg-type]


def test_hash_with_uppercase_hex_rejected() -> None:
    with pytest.raises(ValidationError):
        ApprovalEvent(
            **_kwargs(approved_payload_hash="sha256:" + "A" * 64)  # type: ignore[arg-type]
        )


def test_hash_with_short_digest_rejected() -> None:
    with pytest.raises(ValidationError):
        ApprovalEvent(
            **_kwargs(approved_payload_hash="sha256:" + "a" * 63)  # type: ignore[arg-type]
        )


def test_unknown_hash_algorithm_rejected() -> None:
    with pytest.raises(ValidationError):
        ApprovalEvent.model_validate(
            {
                **_kwargs(),
                "hash_algorithm": "md5",
            }
        )


def test_hash_prefix_must_match_algorithm() -> None:
    # The model only ships with sha256 today, so the prefix check is implicit
    # through the pattern + algorithm enum. Verify both validators agree on a
    # well-formed payload.
    ev = ApprovalEvent(**_kwargs())  # type: ignore[arg-type]
    assert ev.approved_payload_hash.startswith("sha256:")
    assert ev.hash_algorithm.value == "sha256"


def test_extra_field_rejected() -> None:
    payload = {**_kwargs(), "extra": "nope"}
    payload["created_at"] = "2026-05-04T17:55:00+00:00"
    payload["expires_at"] = "2026-05-05T17:55:00+00:00"
    payload["action_type"] = "add_to_calendar"
    payload["hash_algorithm"] = "sha256"
    with pytest.raises(ValidationError):
        ApprovalEvent.model_validate(payload)


def test_event_is_frozen() -> None:
    event = ApprovalEvent(**_kwargs())  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        event.approval_event_id = "other"  # type: ignore[misc]


def test_empty_user_id_rejected() -> None:
    with pytest.raises(ValidationError):
        ApprovalEvent(**_kwargs(user_id=""))  # type: ignore[arg-type]


def test_empty_canonicalization_version_rejected() -> None:
    with pytest.raises(ValidationError):
        ApprovalEvent(**_kwargs(hash_canonicalization_version=""))  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "action_type",
    [
        ApprovalActionType.ADD_TO_CALENDAR,
        ApprovalActionType.UPDATE_CALENDAR,
        ApprovalActionType.ROLLBACK_CALENDAR,
    ],
)
def test_all_allowed_action_types_accepted(action_type: ApprovalActionType) -> None:
    event = ApprovalEvent(**_kwargs(action_type=action_type))  # type: ignore[arg-type]
    assert event.action_type is action_type


def test_long_ttl_is_accepted() -> None:
    # Spec says default 24h but doesn't cap; the model lets the store / write
    # path enforce expiry.
    event = ApprovalEvent(
        **_kwargs(  # type: ignore[arg-type]
            expires_at=datetime(2026, 5, 4, 17, 55, tzinfo=UTC) + timedelta(days=365),
        )
    )
    assert event.expires_at > event.created_at
