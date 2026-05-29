"""Tests for the ``CalendarEventMapping`` contract (Phase 2)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from agentic_calendar.contracts.calendar_event_mapping import (
    CalendarEventMapping,
    CalendarWriteStatus,
)


def _kwargs(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "task_id": "dp_001",
        "plan_version": "plan_001",
        "run_id": "run_001",
        "calendar_event_id": "gcal_evt_001",
        "scheduled_start": datetime(2026, 5, 4, 18, 0, tzinfo=UTC),
        "scheduled_end": datetime(2026, 5, 4, 19, 0, tzinfo=UTC),
        "calendar_write_status": CalendarWriteStatus.WRITTEN,
        "user_modified_bool": False,
        "last_verified_at": None,
    }
    base.update(overrides)
    return base


def test_valid_mapping_constructs() -> None:
    mapping = CalendarEventMapping(**_kwargs())  # type: ignore[arg-type]
    assert mapping.task_id == "dp_001"
    assert mapping.calendar_write_status is CalendarWriteStatus.WRITTEN


def test_round_trip_json() -> None:
    mapping = CalendarEventMapping(**_kwargs())  # type: ignore[arg-type]
    payload = mapping.model_dump(mode="json")
    again = CalendarEventMapping.model_validate(payload)
    assert again == mapping


def test_scheduled_end_must_be_after_start() -> None:
    with pytest.raises(ValidationError, match="strictly after"):
        CalendarEventMapping(
            **_kwargs(  # type: ignore[arg-type]
                scheduled_start=datetime(2026, 5, 4, 19, 0, tzinfo=UTC),
                scheduled_end=datetime(2026, 5, 4, 18, 0, tzinfo=UTC),
            )
        )


def test_scheduled_end_equal_start_rejected() -> None:
    with pytest.raises(ValidationError):
        CalendarEventMapping(
            **_kwargs(  # type: ignore[arg-type]
                scheduled_start=datetime(2026, 5, 4, 19, 0, tzinfo=UTC),
                scheduled_end=datetime(2026, 5, 4, 19, 0, tzinfo=UTC),
            )
        )


def test_naive_scheduled_start_rejected() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        CalendarEventMapping(
            **_kwargs(  # type: ignore[arg-type]
                scheduled_start=datetime(2026, 5, 4, 18, 0),
            )
        )


def test_naive_scheduled_end_rejected() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        CalendarEventMapping(
            **_kwargs(  # type: ignore[arg-type]
                scheduled_end=datetime(2026, 5, 4, 19, 0),
            )
        )


def test_naive_last_verified_at_rejected() -> None:
    with pytest.raises(ValidationError):
        CalendarEventMapping(
            **_kwargs(  # type: ignore[arg-type]
                last_verified_at=datetime(2026, 5, 4, 17, 55),
            )
        )


def test_verified_status_requires_calendar_event_id() -> None:
    with pytest.raises(ValidationError, match="non-null calendar_event_id"):
        CalendarEventMapping(
            **_kwargs(  # type: ignore[arg-type]
                calendar_event_id=None,
                calendar_write_status=CalendarWriteStatus.VERIFIED,
            )
        )


def test_non_verified_statuses_permit_null_event_id() -> None:
    for status in (
        CalendarWriteStatus.DRY_RUN,
        CalendarWriteStatus.WRITTEN,
        CalendarWriteStatus.VERIFICATION_FAILED,
        CalendarWriteStatus.ROLLBACK_PENDING,
        CalendarWriteStatus.ROLLED_BACK,
        CalendarWriteStatus.ROLLBACK_FAILED,
    ):
        # WRITTEN realistically always has an event id; the contract permits
        # null and leaves enforcement to the store / manager.
        mapping = CalendarEventMapping(
            **_kwargs(  # type: ignore[arg-type]
                calendar_event_id=None, calendar_write_status=status
            )
        )
        assert mapping.calendar_event_id is None


def test_extra_field_rejected() -> None:
    payload = {
        **_kwargs(),
        "scheduled_start": "2026-05-04T18:00:00+00:00",
        "scheduled_end": "2026-05-04T19:00:00+00:00",
        "calendar_write_status": "written",
        "extra": "nope",
    }
    with pytest.raises(ValidationError):
        CalendarEventMapping.model_validate(payload)


def test_mapping_is_not_frozen() -> None:
    """Status mutates as writes progress (see ``with_status``)."""
    mapping = CalendarEventMapping(**_kwargs())  # type: ignore[arg-type]
    # extra="forbid" is set, but frozen is NOT; assignment should be allowed.
    mapping.user_modified_bool = True
    assert mapping.user_modified_bool is True


# --------------------------------------------------------------------------- #
# with_status helper
# --------------------------------------------------------------------------- #


def test_with_status_returns_a_copy() -> None:
    mapping = CalendarEventMapping(**_kwargs(last_verified_at=None))  # type: ignore[arg-type]
    now = datetime(2026, 5, 4, 18, 30, tzinfo=UTC)
    updated = mapping.with_status(CalendarWriteStatus.VERIFIED, now=now)
    assert updated.calendar_write_status is CalendarWriteStatus.VERIFIED
    assert updated.last_verified_at == now
    # Original is unchanged.
    assert mapping.calendar_write_status is CalendarWriteStatus.WRITTEN
    assert mapping.last_verified_at is None


def test_with_status_preserves_event_id_when_unset() -> None:
    mapping = CalendarEventMapping(**_kwargs(calendar_event_id="gcal_evt_001"))  # type: ignore[arg-type]
    updated = mapping.with_status(
        CalendarWriteStatus.VERIFIED, now=datetime(2026, 5, 4, 18, 30, tzinfo=UTC)
    )
    assert updated.calendar_event_id == "gcal_evt_001"


def test_with_status_updates_event_id_when_supplied() -> None:
    mapping = CalendarEventMapping(
        **_kwargs(  # type: ignore[arg-type]
            calendar_event_id=None,
            calendar_write_status=CalendarWriteStatus.DRY_RUN,
        )
    )
    updated = mapping.with_status(
        CalendarWriteStatus.WRITTEN,
        now=datetime(2026, 5, 4, 18, 30, tzinfo=UTC),
        calendar_event_id="gcal_evt_new",
    )
    assert updated.calendar_event_id == "gcal_evt_new"
    assert updated.calendar_write_status is CalendarWriteStatus.WRITTEN


def test_with_status_preserves_last_verified_at_on_non_verification_transitions() -> None:
    """``last_verified_at`` is the time the external event was last read back
    from the calendar — not the time the row last changed. Non-verification
    transitions (e.g. ``WRITTEN → ROLLBACK_PENDING``) must NOT overwrite it."""
    verified_at = datetime(2026, 5, 4, 18, 0, tzinfo=UTC)
    mapping = CalendarEventMapping(
        **_kwargs(  # type: ignore[arg-type]
            calendar_write_status=CalendarWriteStatus.VERIFIED,
            calendar_event_id="gcal_evt_001",
            last_verified_at=verified_at,
        )
    )
    later = datetime(2026, 5, 4, 19, 0, tzinfo=UTC)
    updated = mapping.with_status(CalendarWriteStatus.ROLLBACK_PENDING, now=later)
    assert updated.calendar_write_status is CalendarWriteStatus.ROLLBACK_PENDING
    # last_verified_at is unchanged — the event was not re-read.
    assert updated.last_verified_at == verified_at


def test_with_status_stamps_last_verified_at_on_verification_failed() -> None:
    """Both verification outcomes (``VERIFIED`` and ``VERIFICATION_FAILED``)
    are produced by a real read-back, so both stamp ``last_verified_at``."""
    mapping = CalendarEventMapping(
        **_kwargs(  # type: ignore[arg-type]
            calendar_write_status=CalendarWriteStatus.WRITTEN,
            calendar_event_id="gcal_evt_001",
            last_verified_at=None,
        )
    )
    now = datetime(2026, 5, 4, 18, 30, tzinfo=UTC)
    updated = mapping.with_status(CalendarWriteStatus.VERIFICATION_FAILED, now=now)
    assert updated.last_verified_at == now


def test_with_status_to_verified_with_null_event_id_raises() -> None:
    """``with_status`` re-runs validators."""
    mapping = CalendarEventMapping(
        **_kwargs(  # type: ignore[arg-type]
            calendar_event_id=None,
            calendar_write_status=CalendarWriteStatus.WRITTEN,
        )
    )
    with pytest.raises(ValidationError):
        mapping.with_status(
            CalendarWriteStatus.VERIFIED,
            now=datetime(2026, 5, 4, 18, 30, tzinfo=UTC),
        )
