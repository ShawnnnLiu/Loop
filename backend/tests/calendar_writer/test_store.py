"""Tests for ``InMemoryCalendarEventMappingStore`` (Phase 2)."""

from __future__ import annotations

from datetime import UTC, datetime
from itertools import product

import pytest

from agentic_calendar.calendar_writer.store import (
    CalendarEventMappingNotFoundError,
    CalendarEventMappingStore,
    InMemoryCalendarEventMappingStore,
    InvalidStatusTransitionError,
    legal_next_states,
)
from agentic_calendar.contracts.calendar_event_mapping import (
    CalendarEventMapping,
    CalendarWriteStatus,
)


def _mapping(
    *,
    task_id: str = "dp_001",
    run_id: str = "run_001",
    calendar_event_id: str | None = "gcal_evt_001",
    status: CalendarWriteStatus = CalendarWriteStatus.WRITTEN,
) -> CalendarEventMapping:
    return CalendarEventMapping(
        task_id=task_id,
        plan_version="plan_001",
        run_id=run_id,
        calendar_event_id=calendar_event_id,
        scheduled_start=datetime(2026, 5, 4, 18, 0, tzinfo=UTC),
        scheduled_end=datetime(2026, 5, 4, 19, 0, tzinfo=UTC),
        calendar_write_status=status,
        user_modified_bool=False,
        last_verified_at=None,
    )


_NOW = datetime(2026, 5, 4, 17, 55, tzinfo=UTC)


# --------------------------------------------------------------------------- #
# Protocol + basics
# --------------------------------------------------------------------------- #


def test_in_memory_store_satisfies_protocol() -> None:
    assert isinstance(InMemoryCalendarEventMappingStore(), CalendarEventMappingStore)


def test_save_then_get() -> None:
    store = InMemoryCalendarEventMappingStore()
    m = _mapping()
    store.save(m)
    assert store.get("run_001", "dp_001") == m


def test_get_missing_raises() -> None:
    store = InMemoryCalendarEventMappingStore()
    with pytest.raises(CalendarEventMappingNotFoundError):
        store.get("run_x", "task_x")


def test_save_replaces_existing_bucket() -> None:
    """First save inserts; subsequent saves are accepted (transitions go through
    ``update_status``)."""
    store = InMemoryCalendarEventMappingStore()
    store.save(_mapping(calendar_event_id="gcal_evt_a"))
    store.save(_mapping(calendar_event_id="gcal_evt_b"))
    assert store.get("run_001", "dp_001").calendar_event_id == "gcal_evt_b"


def test_list_for_run_returns_insertion_order() -> None:
    store = InMemoryCalendarEventMappingStore()
    store.save(_mapping(task_id="b"))
    store.save(_mapping(task_id="a"))
    store.save(_mapping(task_id="c"))
    listed = store.list_for_run("run_001")
    assert [m.task_id for m in listed] == ["b", "a", "c"]


def test_list_for_run_filters_run_id() -> None:
    store = InMemoryCalendarEventMappingStore()
    store.save(_mapping(task_id="a", run_id="run_a"))
    store.save(_mapping(task_id="b", run_id="run_b"))
    assert [m.task_id for m in store.list_for_run("run_a")] == ["a"]


def test_list_for_task_filters_task_id() -> None:
    store = InMemoryCalendarEventMappingStore()
    store.save(_mapping(task_id="a", run_id="run_1"))
    store.save(_mapping(task_id="b", run_id="run_1"))
    store.save(_mapping(task_id="a", run_id="run_2"))
    listed = store.list_for_task("a")
    assert [m.run_id for m in listed] == ["run_1", "run_2"]


# --------------------------------------------------------------------------- #
# Status transition table
# --------------------------------------------------------------------------- #


_LEGAL_TRANSITIONS: list[tuple[CalendarWriteStatus, CalendarWriteStatus]] = [
    (CalendarWriteStatus.DRY_RUN, CalendarWriteStatus.WRITTEN),
    (CalendarWriteStatus.DRY_RUN, CalendarWriteStatus.ROLLED_BACK),
    (CalendarWriteStatus.WRITTEN, CalendarWriteStatus.VERIFIED),
    (CalendarWriteStatus.WRITTEN, CalendarWriteStatus.VERIFICATION_FAILED),
    (CalendarWriteStatus.WRITTEN, CalendarWriteStatus.ROLLBACK_PENDING),
    (CalendarWriteStatus.VERIFICATION_FAILED, CalendarWriteStatus.ROLLBACK_PENDING),
    (CalendarWriteStatus.VERIFICATION_FAILED, CalendarWriteStatus.WRITTEN),
    (CalendarWriteStatus.ROLLBACK_PENDING, CalendarWriteStatus.ROLLED_BACK),
    (CalendarWriteStatus.ROLLBACK_PENDING, CalendarWriteStatus.ROLLBACK_FAILED),
]


@pytest.mark.parametrize("from_status,to_status", _LEGAL_TRANSITIONS)
def test_legal_transition_accepted(
    from_status: CalendarWriteStatus, to_status: CalendarWriteStatus
) -> None:
    store = InMemoryCalendarEventMappingStore()
    # VERIFIED requires non-null event id; ROLLED_BACK after dry_run has no
    # event id by definition. Pick event-id presence per the destination.
    needs_event_id = to_status is CalendarWriteStatus.VERIFIED
    m = _mapping(
        status=from_status,
        calendar_event_id="gcal_evt_001" if needs_event_id else (
            None if from_status is CalendarWriteStatus.DRY_RUN else "gcal_evt_001"
        ),
    )
    store.save(m)
    updated = store.update_status(
        "run_001", "dp_001", new_status=to_status, now=_NOW
    )
    assert updated.calendar_write_status is to_status


@pytest.mark.parametrize(
    "from_status,to_status",
    [
        pair
        for pair in product(list(CalendarWriteStatus), list(CalendarWriteStatus))
        if pair not in set(_LEGAL_TRANSITIONS) and pair[0] is not pair[1]
    ],
)
def test_illegal_transition_rejected(
    from_status: CalendarWriteStatus, to_status: CalendarWriteStatus
) -> None:
    store = InMemoryCalendarEventMappingStore()
    needs_event_id = from_status is CalendarWriteStatus.VERIFIED
    m = _mapping(
        status=from_status,
        calendar_event_id="gcal_evt_001"
        if needs_event_id
        else (None if from_status is CalendarWriteStatus.DRY_RUN else "gcal_evt_001"),
    )
    store.save(m)
    with pytest.raises(InvalidStatusTransitionError):
        store.update_status(
            "run_001", "dp_001", new_status=to_status, now=_NOW
        )
    # Bucket must remain queryable and unchanged after the illegal transition.
    assert store.get("run_001", "dp_001").calendar_write_status is from_status


def test_update_status_missing_mapping_raises() -> None:
    store = InMemoryCalendarEventMappingStore()
    with pytest.raises(CalendarEventMappingNotFoundError):
        store.update_status(
            "run_x",
            "task_x",
            new_status=CalendarWriteStatus.VERIFIED,
            now=_NOW,
        )


def test_update_status_sets_last_verified_at() -> None:
    store = InMemoryCalendarEventMappingStore()
    store.save(_mapping())
    updated = store.update_status(
        "run_001",
        "dp_001",
        new_status=CalendarWriteStatus.VERIFIED,
        now=_NOW,
    )
    assert updated.last_verified_at == _NOW


def test_update_status_verified_preserves_event_id() -> None:
    store = InMemoryCalendarEventMappingStore()
    store.save(_mapping(calendar_event_id="gcal_evt_42"))
    updated = store.update_status(
        "run_001",
        "dp_001",
        new_status=CalendarWriteStatus.VERIFIED,
        now=_NOW,
    )
    assert updated.calendar_event_id == "gcal_evt_42"


def test_update_status_can_set_event_id() -> None:
    store = InMemoryCalendarEventMappingStore()
    store.save(
        _mapping(
            calendar_event_id=None,
            status=CalendarWriteStatus.DRY_RUN,
        )
    )
    updated = store.update_status(
        "run_001",
        "dp_001",
        new_status=CalendarWriteStatus.WRITTEN,
        now=_NOW,
        calendar_event_id="gcal_evt_first",
    )
    assert updated.calendar_event_id == "gcal_evt_first"


def test_update_status_invariant_failure_rolls_back() -> None:
    """If the resulting mapping fails Pydantic validation, the bucket
    must remain at its prior value."""
    store = InMemoryCalendarEventMappingStore()
    # Start with WRITTEN + valid event id; try to transition to VERIFIED
    # while concurrently clearing the event id is impossible via
    # update_status, so we exercise the invariant via the validator:
    # transition WRITTEN -> VERIFIED is legal, but if the mapping had a null
    # event id (illegally), the Pydantic re-validation would catch it.
    # We construct this state by saving a mapping in WRITTEN with null id
    # (the contract permits this).
    from pydantic import ValidationError

    store.save(_mapping(calendar_event_id=None))
    with pytest.raises(ValidationError):
        store.update_status(
            "run_001",
            "dp_001",
            new_status=CalendarWriteStatus.VERIFIED,
            now=_NOW,
        )
    assert store.get("run_001", "dp_001").calendar_event_id is None


# --------------------------------------------------------------------------- #
# legal_next_states helper
# --------------------------------------------------------------------------- #


def test_legal_next_states_terminal() -> None:
    assert list(legal_next_states(CalendarWriteStatus.VERIFIED)) == []
    assert list(legal_next_states(CalendarWriteStatus.ROLLED_BACK)) == []
    assert list(legal_next_states(CalendarWriteStatus.ROLLBACK_FAILED)) == []


def test_legal_next_states_written() -> None:
    nexts = set(legal_next_states(CalendarWriteStatus.WRITTEN))
    assert nexts == {
        CalendarWriteStatus.VERIFIED,
        CalendarWriteStatus.VERIFICATION_FAILED,
        CalendarWriteStatus.ROLLBACK_PENDING,
    }
