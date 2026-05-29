"""Tests for the raise-only ``GoogleCalendarAdapter`` stub (Phase 2)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from agentic_calendar.calendar_writer.adapter import ExternalCalendarAdapter
from agentic_calendar.calendar_writer.google_adapter import GoogleCalendarAdapter


@pytest.fixture
def adapter() -> GoogleCalendarAdapter:
    return GoogleCalendarAdapter()


def test_satisfies_external_calendar_adapter_protocol(
    adapter: GoogleCalendarAdapter,
) -> None:
    """Even as a stub, the class must satisfy the runtime Protocol so it can
    be wired through dependency-injection scaffolding."""
    assert isinstance(adapter, ExternalCalendarAdapter)


def test_create_event_raises_not_implemented(adapter: GoogleCalendarAdapter) -> None:
    with pytest.raises(NotImplementedError, match="later phase"):
        adapter.create_event(
            target_calendar_id="primary",
            scheduled_start=datetime(2026, 5, 4, 18, 0, tzinfo=UTC),
            scheduled_end=datetime(2026, 5, 4, 19, 0, tzinfo=UTC),
            metadata={"app": "x", "run_id": "y", "plan_version": "z", "task_id": "t"},
        )


def test_read_event_raises_not_implemented(adapter: GoogleCalendarAdapter) -> None:
    with pytest.raises(NotImplementedError):
        adapter.read_event(target_calendar_id="primary", calendar_event_id="evt")


def test_delete_event_raises_not_implemented(adapter: GoogleCalendarAdapter) -> None:
    with pytest.raises(NotImplementedError):
        adapter.delete_event(target_calendar_id="primary", calendar_event_id="evt")


def test_query_events_by_metadata_raises_not_implemented(
    adapter: GoogleCalendarAdapter,
) -> None:
    with pytest.raises(NotImplementedError):
        adapter.query_events_by_metadata(
            target_calendar_id="primary", run_id="run_x"
        )


def test_stub_does_not_import_google_sdk() -> None:
    """The stub must not pull in any Google SDK; importing the module should
    not introduce a top-level ``google`` module dependency."""
    import sys

    # The check is approximate: if some other test already imported google,
    # we can't unset it. Just confirm our module's import has no side effect
    # by importing it fresh and asserting it doesn't add `google.*`.
    before = {n for n in sys.modules if n.startswith("google")}
    import importlib

    import agentic_calendar.calendar_writer.google_adapter as ga

    importlib.reload(ga)
    after = {n for n in sys.modules if n.startswith("google")}
    assert after == before
