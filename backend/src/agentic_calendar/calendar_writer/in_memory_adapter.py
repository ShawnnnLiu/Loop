"""Deterministic in-memory implementation of :class:`ExternalCalendarAdapter`.

Used by the Phase 2 test suite and operator CLIs so the full
preview/write/verify/rollback flow runs without contacting any external
service. Identifiers are produced by the injected :class:`IdGenerator` so
fixture output is byte-stable.

``FailureModes`` exposes the failure injection knobs the test suite needs
without forcing the adapter to grow ad-hoc test hooks: instead of monkey-
patching, callers construct an adapter with the failure modes they want.
"""

from __future__ import annotations

import threading
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime

from agentic_calendar.common.ids import IdGenerator

from .adapter import ExternalEventHandle, ExternalEventRecord

_REQUIRED_METADATA_KEYS = ("app", "run_id", "plan_version", "task_id")


class CalendarAdapterError(Exception):
    """Raised by :class:`InMemoryCalendarAdapter` when a failure mode fires."""


@dataclass(frozen=True, slots=True)
class FailureModes:
    """Test-only injection of adapter failure modes.

    * ``fail_create_for_task_ids``: ``create_event`` raises when ``metadata['task_id']`` matches.
    * ``fail_delete_for_event_ids``: ``delete_event`` raises for matching ids.
    * ``drop_silently_for_task_ids``: ``create_event`` returns a handle but
      no record is stored (simulates an external write that the API claims
      succeeded but is invisible to verification).
    * ``corrupt_metadata_for_task_ids``: stored event records have garbage
      values in ``run_id``/``plan_version``/``task_id`` metadata so
      verification sees a mismatch.
    """

    fail_create_for_task_ids: frozenset[str] = field(default_factory=frozenset)
    fail_delete_for_event_ids: frozenset[str] = field(default_factory=frozenset)
    drop_silently_for_task_ids: frozenset[str] = field(default_factory=frozenset)
    corrupt_metadata_for_task_ids: frozenset[str] = field(default_factory=frozenset)


class InMemoryCalendarAdapter:
    """In-process fake calendar."""

    def __init__(
        self,
        *,
        id_generator: IdGenerator,
        failure_modes: FailureModes | None = None,
    ) -> None:
        self._id_generator = id_generator
        self._failure_modes = failure_modes or FailureModes()
        self._by_id: dict[str, ExternalEventRecord] = {}
        self._order: list[str] = []
        self._lock = threading.RLock()

    def create_event(
        self,
        *,
        target_calendar_id: str,
        scheduled_start: datetime,
        scheduled_end: datetime,
        metadata: Mapping[str, str],
    ) -> ExternalEventHandle:
        missing = [k for k in _REQUIRED_METADATA_KEYS if k not in metadata]
        if missing:
            raise ValueError(
                f"calendar event metadata missing required keys: {missing!r}"
            )
        task_id = metadata["task_id"]
        if task_id in self._failure_modes.fail_create_for_task_ids:
            raise CalendarAdapterError(
                f"injected create_event failure for task_id={task_id!r}"
            )
        with self._lock:
            calendar_event_id = self._id_generator.new_id("gcal_evt")
            stored_metadata = dict(metadata)
            if task_id in self._failure_modes.corrupt_metadata_for_task_ids:
                stored_metadata["run_id"] = f"corrupted_{stored_metadata['run_id']}"
            handle = ExternalEventHandle(
                calendar_event_id=calendar_event_id,
                target_calendar_id=target_calendar_id,
            )
            if task_id in self._failure_modes.drop_silently_for_task_ids:
                return handle
            record = ExternalEventRecord(
                calendar_event_id=calendar_event_id,
                target_calendar_id=target_calendar_id,
                scheduled_start=scheduled_start,
                scheduled_end=scheduled_end,
                metadata=stored_metadata,
            )
            self._by_id[calendar_event_id] = record
            self._order.append(calendar_event_id)
            return handle

    def read_event(
        self,
        *,
        target_calendar_id: str,
        calendar_event_id: str,
    ) -> ExternalEventRecord | None:
        with self._lock:
            record = self._by_id.get(calendar_event_id)
            if record is None or record.target_calendar_id != target_calendar_id:
                return None
            return record

    def delete_event(
        self,
        *,
        target_calendar_id: str,
        calendar_event_id: str,
    ) -> None:
        if calendar_event_id in self._failure_modes.fail_delete_for_event_ids:
            raise CalendarAdapterError(
                f"injected delete_event failure for calendar_event_id={calendar_event_id!r}"
            )
        with self._lock:
            record = self._by_id.get(calendar_event_id)
            if record is None or record.target_calendar_id != target_calendar_id:
                return
            del self._by_id[calendar_event_id]
            self._order.remove(calendar_event_id)

    def query_events_by_metadata(
        self,
        *,
        target_calendar_id: str,
        run_id: str,
    ) -> list[ExternalEventRecord]:
        with self._lock:
            return [
                self._by_id[eid]
                for eid in self._order
                if self._by_id[eid].target_calendar_id == target_calendar_id
                and self._by_id[eid].metadata.get("run_id") == run_id
            ]

    def all_events(self) -> list[ExternalEventRecord]:
        """Inspection helper for tests; returns a snapshot in insertion order."""
        with self._lock:
            return [self._by_id[eid] for eid in self._order]
