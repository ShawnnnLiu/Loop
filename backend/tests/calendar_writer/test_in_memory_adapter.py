"""Tests for ``InMemoryCalendarAdapter`` (Phase 2)."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime

import pytest

from agentic_calendar.calendar_writer.adapter import ExternalCalendarAdapter
from agentic_calendar.calendar_writer.in_memory_adapter import (
    CalendarAdapterError,
    FailureModes,
    InMemoryCalendarAdapter,
)
from agentic_calendar.common.ids import DeterministicIdGenerator


def _meta(
    *,
    run_id: str = "run_001",
    plan_version: str = "plan_001",
    task_id: str = "dp_001",
) -> Mapping[str, str]:
    return {
        "app": "career_scheduler",
        "run_id": run_id,
        "plan_version": plan_version,
        "task_id": task_id,
    }


_START = datetime(2026, 5, 4, 18, 0, tzinfo=UTC)
_END = datetime(2026, 5, 4, 19, 0, tzinfo=UTC)


def _adapter(failure_modes: FailureModes | None = None) -> InMemoryCalendarAdapter:
    return InMemoryCalendarAdapter(
        id_generator=DeterministicIdGenerator(),
        failure_modes=failure_modes,
    )


# --------------------------------------------------------------------------- #
# Protocol conformance + smoke
# --------------------------------------------------------------------------- #


def test_satisfies_protocol() -> None:
    assert isinstance(_adapter(), ExternalCalendarAdapter)


def test_create_read_round_trip() -> None:
    a = _adapter()
    handle = a.create_event(
        target_calendar_id="primary",
        scheduled_start=_START,
        scheduled_end=_END,
        metadata=_meta(),
    )
    record = a.read_event(
        target_calendar_id="primary",
        calendar_event_id=handle.calendar_event_id,
    )
    assert record is not None
    assert record.calendar_event_id == handle.calendar_event_id
    assert record.scheduled_start == _START
    assert record.scheduled_end == _END
    assert record.metadata == _meta()


def test_event_id_uses_deterministic_prefix() -> None:
    a = _adapter()
    h1 = a.create_event(
        target_calendar_id="primary",
        scheduled_start=_START,
        scheduled_end=_END,
        metadata=_meta(task_id="t1"),
    )
    h2 = a.create_event(
        target_calendar_id="primary",
        scheduled_start=_START,
        scheduled_end=_END,
        metadata=_meta(task_id="t2"),
    )
    assert h1.calendar_event_id.startswith("gcal_evt_")
    assert h2.calendar_event_id.startswith("gcal_evt_")
    assert h1.calendar_event_id != h2.calendar_event_id


def test_delete_event_removes_it() -> None:
    a = _adapter()
    handle = a.create_event(
        target_calendar_id="primary",
        scheduled_start=_START,
        scheduled_end=_END,
        metadata=_meta(),
    )
    a.delete_event(
        target_calendar_id="primary",
        calendar_event_id=handle.calendar_event_id,
    )
    assert (
        a.read_event(
            target_calendar_id="primary",
            calendar_event_id=handle.calendar_event_id,
        )
        is None
    )


def test_delete_unknown_id_is_no_op() -> None:
    a = _adapter()
    a.delete_event(target_calendar_id="primary", calendar_event_id="nope")  # no raise


def test_read_unknown_id_returns_none() -> None:
    a = _adapter()
    assert (
        a.read_event(target_calendar_id="primary", calendar_event_id="nope")
        is None
    )


def test_read_with_wrong_target_calendar_returns_none() -> None:
    a = _adapter()
    handle = a.create_event(
        target_calendar_id="primary",
        scheduled_start=_START,
        scheduled_end=_END,
        metadata=_meta(),
    )
    assert (
        a.read_event(
            target_calendar_id="secondary",
            calendar_event_id=handle.calendar_event_id,
        )
        is None
    )


# --------------------------------------------------------------------------- #
# Metadata invariants
# --------------------------------------------------------------------------- #


def test_create_rejects_metadata_missing_app() -> None:
    a = _adapter()
    bad = dict(_meta())
    del bad["app"]
    with pytest.raises(ValueError, match="missing required keys"):
        a.create_event(
            target_calendar_id="primary",
            scheduled_start=_START,
            scheduled_end=_END,
            metadata=bad,
        )


@pytest.mark.parametrize("missing", ["app", "run_id", "plan_version", "task_id"])
def test_create_rejects_each_missing_metadata_key(missing: str) -> None:
    a = _adapter()
    bad = dict(_meta())
    del bad[missing]
    with pytest.raises(ValueError, match=missing):
        a.create_event(
            target_calendar_id="primary",
            scheduled_start=_START,
            scheduled_end=_END,
            metadata=bad,
        )


def test_create_accepts_extra_metadata_keys() -> None:
    """Extra keys are allowed (the spec only mandates the four canonical ones)."""
    a = _adapter()
    md = {**_meta(), "extra": "value"}
    handle = a.create_event(
        target_calendar_id="primary",
        scheduled_start=_START,
        scheduled_end=_END,
        metadata=md,
    )
    record = a.read_event(
        target_calendar_id="primary",
        calendar_event_id=handle.calendar_event_id,
    )
    assert record is not None
    assert record.metadata["extra"] == "value"


# --------------------------------------------------------------------------- #
# query_events_by_metadata
# --------------------------------------------------------------------------- #


def test_query_by_metadata_filters_run_id() -> None:
    a = _adapter()
    for tid in ("t1", "t2"):
        a.create_event(
            target_calendar_id="primary",
            scheduled_start=_START,
            scheduled_end=_END,
            metadata=_meta(run_id="run_keep", task_id=tid),
        )
    a.create_event(
        target_calendar_id="primary",
        scheduled_start=_START,
        scheduled_end=_END,
        metadata=_meta(run_id="run_drop", task_id="t3"),
    )
    keep = a.query_events_by_metadata(target_calendar_id="primary", run_id="run_keep")
    assert {ev.metadata["task_id"] for ev in keep} == {"t1", "t2"}


def test_query_by_metadata_filters_target_calendar() -> None:
    a = _adapter()
    a.create_event(
        target_calendar_id="primary",
        scheduled_start=_START,
        scheduled_end=_END,
        metadata=_meta(),
    )
    assert (
        a.query_events_by_metadata(target_calendar_id="secondary", run_id="run_001")
        == []
    )


def test_query_returns_empty_when_no_matches() -> None:
    a = _adapter()
    assert a.query_events_by_metadata(target_calendar_id="primary", run_id="x") == []


# --------------------------------------------------------------------------- #
# FailureModes
# --------------------------------------------------------------------------- #


def test_fail_create_for_task_ids_raises() -> None:
    a = _adapter(FailureModes(fail_create_for_task_ids=frozenset({"dp_001"})))
    with pytest.raises(CalendarAdapterError):
        a.create_event(
            target_calendar_id="primary",
            scheduled_start=_START,
            scheduled_end=_END,
            metadata=_meta(task_id="dp_001"),
        )


def test_fail_create_does_not_affect_other_tasks() -> None:
    a = _adapter(FailureModes(fail_create_for_task_ids=frozenset({"bad"})))
    handle = a.create_event(
        target_calendar_id="primary",
        scheduled_start=_START,
        scheduled_end=_END,
        metadata=_meta(task_id="ok"),
    )
    assert handle.calendar_event_id


def test_fail_delete_for_event_ids_raises() -> None:
    a = _adapter()
    handle = a.create_event(
        target_calendar_id="primary",
        scheduled_start=_START,
        scheduled_end=_END,
        metadata=_meta(),
    )
    # Re-wire with the failure mode on this specific id.
    a2 = InMemoryCalendarAdapter(
        id_generator=DeterministicIdGenerator(),
        failure_modes=FailureModes(
            fail_delete_for_event_ids=frozenset({handle.calendar_event_id})
        ),
    )
    with pytest.raises(CalendarAdapterError):
        a2.delete_event(
            target_calendar_id="primary",
            calendar_event_id=handle.calendar_event_id,
        )


def test_drop_silently_returns_handle_but_no_record() -> None:
    a = _adapter(FailureModes(drop_silently_for_task_ids=frozenset({"dp_001"})))
    handle = a.create_event(
        target_calendar_id="primary",
        scheduled_start=_START,
        scheduled_end=_END,
        metadata=_meta(task_id="dp_001"),
    )
    # The adapter returns a handle but the event is invisible.
    assert (
        a.read_event(
            target_calendar_id="primary",
            calendar_event_id=handle.calendar_event_id,
        )
        is None
    )
    assert a.all_events() == []


def test_corrupt_metadata_changes_run_id() -> None:
    a = _adapter(FailureModes(corrupt_metadata_for_task_ids=frozenset({"dp_001"})))
    handle = a.create_event(
        target_calendar_id="primary",
        scheduled_start=_START,
        scheduled_end=_END,
        metadata=_meta(task_id="dp_001"),
    )
    record = a.read_event(
        target_calendar_id="primary",
        calendar_event_id=handle.calendar_event_id,
    )
    assert record is not None
    assert record.metadata["run_id"].startswith("corrupted_")


# --------------------------------------------------------------------------- #
# all_events inspection
# --------------------------------------------------------------------------- #


def test_all_events_in_insertion_order() -> None:
    a = _adapter()
    handles = []
    for tid in ("a", "b", "c"):
        handles.append(
            a.create_event(
                target_calendar_id="primary",
                scheduled_start=_START,
                scheduled_end=_END,
                metadata=_meta(task_id=tid),
            )
        )
    recs = a.all_events()
    assert [r.calendar_event_id for r in recs] == [h.calendar_event_id for h in handles]
