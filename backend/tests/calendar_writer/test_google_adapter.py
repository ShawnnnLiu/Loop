"""Tests for the real ``GoogleCalendarAdapter`` (Phase 9c).

Everything runs against an in-test :class:`FakeGoogleTransport` that speaks
real-shape Calendar v3 ``Event`` resources — no network, no
``googleapiclient`` import. The suite pins the adapter-level safety
properties (dedicated-calendar guard, content-free event bodies, cancelled →
absent translation) and then re-runs the axiom 06 manager flow —
preview / approval / write / verify / duplicate guard / rollback — with the
Google adapter underneath, proving the manager invariants survive the swap
from the in-memory adapter unchanged.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

import pytest

from agentic_calendar.approval.store import InMemoryApprovalEventStore
from agentic_calendar.calendar_writer.adapter import (
    ExternalCalendarAdapter,
    ExternalEventRecord,
)
from agentic_calendar.calendar_writer.errors import CalendarWriterError
from agentic_calendar.calendar_writer.google_adapter import (
    EVENT_SUMMARY,
    DedicatedCalendarViolationError,
    GoogleApiHttpTransport,
    GoogleCalendarAdapter,
    GoogleCalendarApiError,
    GoogleCalendarTransport,
)
from agentic_calendar.calendar_writer.lock import CalendarWriteLockManager
from agentic_calendar.calendar_writer.manager import (
    CalendarWriteManager,
    WriteStatus,
)
from agentic_calendar.calendar_writer.metadata import APP_TAG, build_event_metadata
from agentic_calendar.calendar_writer.store import (
    InMemoryCalendarEventMappingStore,
)
from agentic_calendar.common.clock import FrozenClock
from agentic_calendar.common.ids import DeterministicIdGenerator
from agentic_calendar.contracts.approval_event import (
    ApprovalActionType,
    ApprovalEvent,
    HashAlgorithm,
)
from agentic_calendar.contracts.calendar_event_mapping import CalendarWriteStatus
from agentic_calendar.contracts.draft_schedule import (
    DraftSchedule,
    DraftScheduleEntry,
)
from agentic_calendar.contracts.hashing import canonical_payload_hash
from agentic_calendar.contracts.reason_codes import ReasonCode

_DEDICATED = "career_prep_abc123@group.calendar.google.com"
_NOW = datetime(2026, 5, 4, 17, 55, tzinfo=UTC)
_START = datetime(2026, 5, 4, 18, 0, tzinfo=UTC)
_END = datetime(2026, 5, 4, 19, 0, tzinfo=UTC)


class FakeGoogleTransport:
    """In-test :class:`GoogleCalendarTransport` over real-shape v3 resources.

    Mirrors the live transport's documented contract:

    * deterministic event ids ``gcal_evt_1``, ``gcal_evt_2``, ...;
    * ``get_event`` returns the stored resource INCLUDING cancelled ones —
      like the real API after a delete (Google soft-deletes) — so the
      adapter's cancelled→``None`` translation is actually exercised;
    * ``delete_event`` soft-deletes (``status="cancelled"``) and is a silent
      no-op for unknown ids (the 404/410 path);
    * ``list_events`` matches every requested private property and returns
      cancelled items too — the adapter must filter them;
    * non-absent failures raise :class:`GoogleCalendarApiError` directly,
      the typed error the transport contract promises (no
      ``googleapiclient`` in tests): set ``fail_insert`` / ``fail_list`` to
      raise it on the next insert / list (one-shot, then cleared);
    * every ``(method, calendar_id)`` call is recorded in ``calls`` so tests
      can prove the dedicated-calendar guard fires BEFORE any transport I/O.
    """

    def __init__(self) -> None:
        self.events: dict[str, dict[str, Any]] = {}
        self.calls: list[tuple[str, str]] = []
        self.fail_insert: GoogleCalendarApiError | None = None
        self.fail_list: GoogleCalendarApiError | None = None
        self._counter = 0

    def insert_event(
        self, *, calendar_id: str, body: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        self.calls.append(("insert_event", calendar_id))
        if self.fail_insert is not None:
            error, self.fail_insert = self.fail_insert, None
            raise error
        self._counter += 1
        event_id = f"gcal_evt_{self._counter}"
        resource: dict[str, Any] = {
            "id": event_id,
            "status": "confirmed",
            "summary": body["summary"],
            "start": dict(body["start"]),
            "end": dict(body["end"]),
            "extendedProperties": {
                "private": dict(body["extendedProperties"]["private"])
            },
        }
        self.events[event_id] = resource
        return resource

    def get_event(
        self, *, calendar_id: str, event_id: str
    ) -> Mapping[str, Any] | None:
        self.calls.append(("get_event", calendar_id))
        return self.events.get(event_id)

    def delete_event(self, *, calendar_id: str, event_id: str) -> None:
        self.calls.append(("delete_event", calendar_id))
        resource = self.events.get(event_id)
        if resource is None:
            return  # 404/410 translate to a silent no-op per the contract
        resource["status"] = "cancelled"

    def list_events(
        self, *, calendar_id: str, private_properties: Mapping[str, str]
    ) -> list[Mapping[str, Any]]:
        self.calls.append(("list_events", calendar_id))
        if self.fail_list is not None:
            error, self.fail_list = self.fail_list, None
            raise error
        return [
            resource
            for resource in self.events.values()
            if all(
                resource.get("extendedProperties", {}).get("private", {}).get(key)
                == value
                for key, value in private_properties.items()
            )
        ]


def _make_adapter() -> tuple[GoogleCalendarAdapter, FakeGoogleTransport]:
    transport = FakeGoogleTransport()
    adapter = GoogleCalendarAdapter(
        transport=transport, dedicated_calendar_id=_DEDICATED
    )
    return adapter, transport


def _metadata(run_id: str = "run_001", task_id: str = "t1") -> dict[str, str]:
    return build_event_metadata(
        run_id=run_id, plan_version="plan_001", task_id=task_id
    )


# --------------------------------------------------------------------------- #
# protocol satisfaction
# --------------------------------------------------------------------------- #


def test_satisfies_external_calendar_adapter_protocol() -> None:
    """The real adapter must be swappable wherever the in-memory adapter is
    wired (the manager depends only on the Protocol), and the fake transport
    must satisfy the transport seam the live transport implements."""
    adapter, transport = _make_adapter()
    assert isinstance(adapter, ExternalCalendarAdapter)
    assert isinstance(transport, GoogleCalendarTransport)


def test_google_adapter_errors_are_calendar_writer_errors() -> None:
    """The manager's boundary translation catches ``CalendarWriterError``;
    the Google error hierarchy must live under it so every transport/adapter
    failure inside the write path becomes a typed ``WriteResult`` with the
    lock released, never a raw exception that strands the run (axiom 06/16)."""
    assert isinstance(GoogleCalendarApiError("x"), CalendarWriterError)
    assert isinstance(
        DedicatedCalendarViolationError(requested="primary", dedicated=_DEDICATED),
        CalendarWriterError,
    )


# --------------------------------------------------------------------------- #
# dedicated-calendar guard
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("bad_calendar_id", ["primary", ""])
def test_constructor_rejects_primary_and_empty_calendar(
    bad_calendar_id: str,
) -> None:
    """The adapter can never be bound to the user's primary calendar (or to
    nothing): the system must be structurally incapable of writing into
    personal events, whatever the composition root passes."""
    with pytest.raises(DedicatedCalendarViolationError):
        GoogleCalendarAdapter(
            transport=FakeGoogleTransport(), dedicated_calendar_id=bad_calendar_id
        )


@pytest.mark.parametrize(
    "bad_target",
    ["primary", "", "someone_else@group.calendar.google.com"],
)
def test_every_method_guards_target_before_any_transport_io(
    bad_target: str,
) -> None:
    """A mismatched ``target_calendar_id`` on any of the four methods raises
    BEFORE any transport call — zero I/O ever reaches the wrong calendar."""
    adapter, transport = _make_adapter()
    with pytest.raises(DedicatedCalendarViolationError) as exc_info:
        adapter.create_event(
            target_calendar_id=bad_target,
            scheduled_start=_START,
            scheduled_end=_END,
            metadata=_metadata(),
        )
    assert exc_info.value.requested == bad_target
    with pytest.raises(DedicatedCalendarViolationError):
        adapter.read_event(target_calendar_id=bad_target, calendar_event_id="gcal_evt_1")
    with pytest.raises(DedicatedCalendarViolationError):
        adapter.delete_event(
            target_calendar_id=bad_target, calendar_event_id="gcal_evt_1"
        )
    with pytest.raises(DedicatedCalendarViolationError):
        adapter.query_events_by_metadata(
            target_calendar_id=bad_target, run_id="run_001"
        )
    # The guard fired before transport I/O in every case.
    assert transport.calls == []


# --------------------------------------------------------------------------- #
# create_event body shape
# --------------------------------------------------------------------------- #


def test_create_event_body_is_content_free_and_utc() -> None:
    """The wire body carries the fixed content-free summary, UTC dateTime
    bounds, and exactly the canonical metadata under
    ``extendedProperties.private`` — no raw task titles or descriptions ever
    reach the external calendar (axiom 06). ``create_event`` has no
    title/description parameter at all; the only free-text field is the
    ``EVENT_SUMMARY`` constant."""
    adapter, transport = _make_adapter()
    metadata = _metadata()
    # Non-UTC inputs must be converted, not passed through.
    minus_four = timezone(timedelta(hours=-4))
    handle = adapter.create_event(
        target_calendar_id=_DEDICATED,
        scheduled_start=datetime(2026, 5, 4, 14, 0, tzinfo=minus_four),
        scheduled_end=datetime(2026, 5, 4, 15, 0, tzinfo=minus_four),
        metadata=metadata,
    )
    assert handle.calendar_event_id == "gcal_evt_1"
    assert handle.target_calendar_id == _DEDICATED

    resource = transport.events["gcal_evt_1"]
    assert resource["summary"] == EVENT_SUMMARY
    assert resource["start"] == {
        "dateTime": "2026-05-04T18:00:00+00:00",
        "timeZone": "UTC",
    }
    assert resource["end"] == {
        "dateTime": "2026-05-04T19:00:00+00:00",
        "timeZone": "UTC",
    }
    # Full canonical metadata, exactly as build_event_metadata produces it.
    assert resource["extendedProperties"]["private"] == metadata
    assert set(metadata) == {"app", "run_id", "plan_version", "task_id"}
    # No description or other content fields in the stored resource.
    assert set(resource) == {
        "id",
        "status",
        "summary",
        "start",
        "end",
        "extendedProperties",
    }


# --------------------------------------------------------------------------- #
# read_event
# --------------------------------------------------------------------------- #


def test_read_event_round_trip() -> None:
    """A created event reads back as an ``ExternalEventRecord`` with the same
    id, UTC times, and metadata — the record the verifier compares against."""
    adapter, _transport = _make_adapter()
    metadata = _metadata()
    handle = adapter.create_event(
        target_calendar_id=_DEDICATED,
        scheduled_start=_START,
        scheduled_end=_END,
        metadata=metadata,
    )
    record = adapter.read_event(
        target_calendar_id=_DEDICATED, calendar_event_id=handle.calendar_event_id
    )
    assert record == ExternalEventRecord(
        calendar_event_id=handle.calendar_event_id,
        target_calendar_id=_DEDICATED,
        scheduled_start=_START,
        scheduled_end=_END,
        metadata=metadata,
    )


def test_read_event_absent_returns_none() -> None:
    adapter, _transport = _make_adapter()
    assert (
        adapter.read_event(
            target_calendar_id=_DEDICATED, calendar_event_id="never_existed"
        )
        is None
    )


def test_read_event_translates_cancelled_to_none() -> None:
    """Google soft-deletes: the API keeps returning the event with
    ``status=cancelled``. For verification/rollback semantics that IS absent,
    so the adapter must translate it to ``None`` — the same answer the
    in-memory adapter gives after a hard delete."""
    adapter, transport = _make_adapter()
    handle = adapter.create_event(
        target_calendar_id=_DEDICATED,
        scheduled_start=_START,
        scheduled_end=_END,
        metadata=_metadata(),
    )
    adapter.delete_event(
        target_calendar_id=_DEDICATED, calendar_event_id=handle.calendar_event_id
    )
    # The transport still serves the cancelled resource (real API behavior)...
    raw = transport.get_event(
        calendar_id=_DEDICATED, event_id=handle.calendar_event_id
    )
    assert raw is not None
    assert raw["status"] == "cancelled"
    # ...so a None here proves the ADAPTER did the translation.
    assert (
        adapter.read_event(
            target_calendar_id=_DEDICATED,
            calendar_event_id=handle.calendar_event_id,
        )
        is None
    )


def test_read_event_all_day_resource_raises_typed_error() -> None:
    """An all-day event (``start.date`` instead of ``start.dateTime``) was not
    created by this system; it must fail loudly with the typed error rather
    than be silently coerced into a record."""
    adapter, transport = _make_adapter()
    transport.events["evt_allday"] = {
        "id": "evt_allday",
        "status": "confirmed",
        "summary": "Foreign all-day event",
        "start": {"date": "2026-05-04"},
        "end": {"date": "2026-05-05"},
        "extendedProperties": {"private": {}},
    }
    with pytest.raises(GoogleCalendarApiError, match="dateTime"):
        adapter.read_event(
            target_calendar_id=_DEDICATED, calendar_event_id="evt_allday"
        )


# --------------------------------------------------------------------------- #
# query_events_by_metadata
# --------------------------------------------------------------------------- #


def test_query_by_metadata_filters_app_run_and_cancelled() -> None:
    """The duplicate guard's query must see exactly the live events tagged
    ``app=APP_TAG`` + the requested ``run_id``: other runs are excluded and
    cancelled (soft-deleted) events do not count as duplicates."""
    adapter, transport = _make_adapter()
    keep = adapter.create_event(
        target_calendar_id=_DEDICATED,
        scheduled_start=_START,
        scheduled_end=_END,
        metadata=_metadata(run_id="run_001", task_id="t1"),
    )
    cancelled = adapter.create_event(
        target_calendar_id=_DEDICATED,
        scheduled_start=_START,
        scheduled_end=_END,
        metadata=_metadata(run_id="run_001", task_id="t2"),
    )
    adapter.create_event(
        target_calendar_id=_DEDICATED,
        scheduled_start=_START,
        scheduled_end=_END,
        metadata=_metadata(run_id="run_OTHER", task_id="t9"),
    )
    adapter.delete_event(
        target_calendar_id=_DEDICATED, calendar_event_id=cancelled.calendar_event_id
    )

    # The transport's raw listing still includes the cancelled run_001 event
    # (real API behavior), so the filtering below is the adapter's doing.
    raw = transport.list_events(
        calendar_id=_DEDICATED,
        private_properties={"app": APP_TAG, "run_id": "run_001"},
    )
    assert {item["id"] for item in raw} == {
        keep.calendar_event_id,
        cancelled.calendar_event_id,
    }

    records = adapter.query_events_by_metadata(
        target_calendar_id=_DEDICATED, run_id="run_001"
    )
    assert [r.calendar_event_id for r in records] == [keep.calendar_event_id]
    assert records[0].metadata["app"] == APP_TAG
    assert records[0].metadata["run_id"] == "run_001"


# --------------------------------------------------------------------------- #
# delete_event
# --------------------------------------------------------------------------- #


def test_delete_event_is_idempotent() -> None:
    """Rollback retries must be safe: deleting twice and deleting an unknown
    id are silent no-ops (axiom 06 rollback semantics), and the event reads
    back as absent afterwards."""
    adapter, _transport = _make_adapter()
    handle = adapter.create_event(
        target_calendar_id=_DEDICATED,
        scheduled_start=_START,
        scheduled_end=_END,
        metadata=_metadata(),
    )
    adapter.delete_event(
        target_calendar_id=_DEDICATED, calendar_event_id=handle.calendar_event_id
    )
    # Second delete of the same (now cancelled) event: no raise.
    adapter.delete_event(
        target_calendar_id=_DEDICATED, calendar_event_id=handle.calendar_event_id
    )
    # Delete of an id that never existed: no raise.
    adapter.delete_event(
        target_calendar_id=_DEDICATED, calendar_event_id="never_existed"
    )
    assert (
        adapter.read_event(
            target_calendar_id=_DEDICATED,
            calendar_event_id=handle.calendar_event_id,
        )
        is None
    )


# --------------------------------------------------------------------------- #
# manager integration — the axiom 06 flow over the Google adapter
# --------------------------------------------------------------------------- #


def _draft(
    entries: tuple[DraftScheduleEntry, ...] | None = None,
    draft_schedule_id: str = "draft_001",
    plan_version: str = "plan_001",
) -> DraftSchedule:
    return DraftSchedule(
        draft_schedule_id=draft_schedule_id,
        plan_version=plan_version,
        entries=entries
        or (
            DraftScheduleEntry(
                task_id="t1",
                start=datetime(2026, 5, 4, 18, 0, tzinfo=UTC),
                end=datetime(2026, 5, 4, 19, 0, tzinfo=UTC),
            ),
            DraftScheduleEntry(
                task_id="t2",
                start=datetime(2026, 5, 4, 20, 0, tzinfo=UTC),
                end=datetime(2026, 5, 4, 21, 0, tzinfo=UTC),
            ),
        ),
        created_at=_NOW,
    )


def _approval_for(
    draft: DraftSchedule,
    *,
    user_id: str = "user_a",
    approval_event_id: str = "approval_001",
) -> ApprovalEvent:
    return ApprovalEvent(
        approval_event_id=approval_event_id,
        user_id=user_id,
        plan_id=draft.plan_version,
        draft_schedule_id=draft.draft_schedule_id,
        action_type=ApprovalActionType.ADD_TO_CALENDAR,
        approved_payload_hash=canonical_payload_hash(draft, "v1"),
        hash_algorithm=HashAlgorithm.SHA256,
        hash_canonicalization_version="v1",
        created_at=_NOW,
        expires_at=_NOW + timedelta(hours=24),
    )


def _make_google_manager() -> tuple[
    CalendarWriteManager,
    GoogleCalendarAdapter,
    FakeGoogleTransport,
    InMemoryCalendarEventMappingStore,
    InMemoryApprovalEventStore,
]:
    clk = FrozenClock(_NOW)
    id_gen = DeterministicIdGenerator()
    transport = FakeGoogleTransport()
    adapter = GoogleCalendarAdapter(
        transport=transport, dedicated_calendar_id=_DEDICATED
    )
    mapping_store = InMemoryCalendarEventMappingStore()
    approval_store = InMemoryApprovalEventStore()
    lock = CalendarWriteLockManager(clock=clk)
    mgr = CalendarWriteManager(
        adapter=adapter,
        mapping_store=mapping_store,
        approval_store=approval_store,
        lock_manager=lock,
        id_generator=id_gen,
        clock=clk,
    )
    return mgr, adapter, transport, mapping_store, approval_store


def test_manager_full_lifecycle_over_google_adapter() -> None:
    """The full axiom 06 flow — preview, approval, hash-rechecked write,
    verification read-back, rollback by stored mapping — works unchanged with
    the Google adapter underneath the manager."""
    mgr, adapter, transport, mapping_store, approval_store = _make_google_manager()
    draft = _draft()

    preview = mgr.preview(draft=draft, target_calendar_id=_DEDICATED)
    assert preview.draft_payload_hash == canonical_payload_hash(draft, "v1")
    # Preview is pure: no transport I/O whatsoever.
    assert transport.calls == []

    approval = _approval_for(draft)
    approval_store.save(approval)
    result = mgr.approve_and_write(
        approval_event_id=approval.approval_event_id,
        draft=draft,
        target_calendar_id=_DEDICATED,
    )
    assert result.status is WriteStatus.SUCCESS
    assert result.reason_code is None
    assert result.run_id is not None
    assert result.verification is not None
    assert result.verification.all_verified
    mappings = mapping_store.list_for_run(result.run_id)
    assert len(mappings) == 2
    assert {m.calendar_write_status for m in mappings} == {
        CalendarWriteStatus.VERIFIED
    }
    assert len(transport.events) == 2

    rollback = mgr.rollback(run_id=result.run_id, target_calendar_id=_DEDICATED)
    assert rollback.fully_rolled_back
    for mapping in mapping_store.list_for_run(result.run_id):
        assert mapping.calendar_write_status is CalendarWriteStatus.ROLLED_BACK
        assert mapping.calendar_event_id is not None
        # Cancelled events read back as absent through the adapter.
        assert (
            adapter.read_event(
                target_calendar_id=_DEDICATED,
                calendar_event_id=mapping.calendar_event_id,
            )
            is None
        )
    # Google soft-delete: the cancelled resources remain on the wire.
    assert all(r["status"] == "cancelled" for r in transport.events.values())


def test_manager_duplicate_detected_aborts_pre_write_over_google_adapter() -> None:
    """Pre-write metadata query finds an in-flight event tagged with the same
    run_id (axiom 06 duplicate detection by metadata) → ABORTED_PRE_WRITE with
    CALENDAR_WRITE_DUPLICATE_DETECTED and zero further inserts."""
    mgr, adapter, transport, mapping_store, approval_store = _make_google_manager()
    draft = _draft()
    approval = _approval_for(draft)
    approval_store.save(approval)

    # DeterministicIdGenerator emits "run_001" on the first new_id("run")
    # call, which is what approve_and_write will use. Pre-stage an event
    # tagged with that run_id to simulate a previous in-flight write the
    # duplicate guard must catch.
    adapter.create_event(
        target_calendar_id=_DEDICATED,
        scheduled_start=_START,
        scheduled_end=_END,
        metadata=build_event_metadata(
            run_id="run_001", plan_version=draft.plan_version, task_id="t1"
        ),
    )
    pre_write_event_count = len(transport.events)

    result = mgr.approve_and_write(
        approval_event_id=approval.approval_event_id,
        draft=draft,
        target_calendar_id=_DEDICATED,
    )
    assert result.status is WriteStatus.ABORTED_PRE_WRITE
    assert result.reason_code is ReasonCode.CALENDAR_WRITE_DUPLICATE_DETECTED
    assert result.run_id == "run_001"
    assert result.written_mappings == ()
    # No new events created; the only insert is the pre-staged one.
    assert len(transport.events) == pre_write_event_count
    assert transport.calls.count(("insert_event", _DEDICATED)) == 1
    # No mappings persisted under the colliding run_id.
    assert mapping_store.list_for_run("run_001") == []


def test_manager_insert_failure_surfaces_calendar_write_failed() -> None:
    """A transport-level insert failure (the typed GoogleCalendarApiError)
    becomes a PARTIAL_FAILURE WriteResult with the typed reason_code
    CALENDAR_WRITE_FAILED — never a silent or untyped failure (axiom 06)."""
    mgr, _adapter, transport, mapping_store, approval_store = _make_google_manager()
    draft = _draft()
    approval = _approval_for(draft)
    approval_store.save(approval)
    transport.fail_insert = GoogleCalendarApiError(
        "events.insert failed: backend error", status=500
    )

    result = mgr.approve_and_write(
        approval_event_id=approval.approval_event_id,
        draft=draft,
        target_calendar_id=_DEDICATED,
    )
    assert result.status is WriteStatus.PARTIAL_FAILURE
    assert result.reason_code is ReasonCode.CALENDAR_WRITE_FAILED
    assert result.run_id is not None
    # The first insert failed, so nothing was stored externally or locally.
    assert transport.events == {}
    assert mapping_store.list_for_run(result.run_id) == []


def test_manager_list_failure_returns_typed_result_and_releases_lock() -> None:
    """A transport-level list failure during the duplicate guard (the live
    dogfood failure mode) must RETURN a typed WriteResult — never raise past
    the manager boundary — and must leave the per-user lock released so the
    user is not stranded (axiom 06/16)."""
    clk = FrozenClock(_NOW)
    transport = FakeGoogleTransport()
    adapter = GoogleCalendarAdapter(
        transport=transport, dedicated_calendar_id=_DEDICATED
    )
    mapping_store = InMemoryCalendarEventMappingStore()
    approval_store = InMemoryApprovalEventStore()
    lock = CalendarWriteLockManager(clock=clk)
    mgr = CalendarWriteManager(
        adapter=adapter,
        mapping_store=mapping_store,
        approval_store=approval_store,
        lock_manager=lock,
        id_generator=DeterministicIdGenerator(),
        clock=clk,
    )
    draft = _draft()
    approval = _approval_for(draft)
    approval_store.save(approval)
    transport.fail_list = GoogleCalendarApiError(
        "events.list failed for calendar "
        f"{_DEDICATED!r}: HTTP 403: insufficient permissions",
        status=403,
    )

    result = mgr.approve_and_write(
        approval_event_id=approval.approval_event_id,
        draft=draft,
        target_calendar_id=_DEDICATED,
    )

    # Typed failure, not a raise: the inherited CALENDAR_WRITE_FAILED code.
    assert result.status is WriteStatus.PARTIAL_FAILURE
    assert result.reason_code is ReasonCode.CALENDAR_WRITE_FAILED
    assert result.run_id is not None
    assert result.written_mappings == ()
    # The adapter's enriched provider detail reaches the operator — the
    # reason_code alone would hide which API call failed and why.
    assert result.error is not None
    assert "events.list failed" in result.error
    # The guard failed before any insert: nothing external, nothing local.
    assert transport.events == {}
    assert mapping_store.list_for_run(result.run_id) == []
    # The lock was released on the way out (finally), so the same user can
    # immediately acquire it again — no stranded in-progress run.
    token = lock.acquire(user_id=approval.user_id, run_id="run_retry")
    lock.release(token)


# --------------------------------------------------------------------------- #
# free/busy read (feeds the scheduler the user's existing commitments)
# --------------------------------------------------------------------------- #


class _FakeFreeBusyService:
    """Minimal Calendar v3 service exposing only ``freebusy().query().execute()``."""

    def __init__(self, response: Mapping[str, Any]) -> None:
        self._response = response
        self.queries: list[Mapping[str, Any]] = []

    def freebusy(self) -> _FakeFreeBusyService:
        return self

    def query(self, *, body: Mapping[str, Any]) -> _FakeFreeBusyService:
        self.queries.append(body)
        return self

    def execute(self) -> Mapping[str, Any]:
        return self._response


def test_query_free_busy_parses_ranges_and_sends_window() -> None:
    service = _FakeFreeBusyService(
        {
            "calendars": {
                "primary": {
                    "busy": [
                        {"start": "2026-05-04T01:00:00Z", "end": "2026-05-04T03:00:00+00:00"}
                    ]
                }
            }
        }
    )
    transport = GoogleApiHttpTransport(service)
    time_min = datetime(2026, 5, 4, tzinfo=UTC)
    time_max = time_min + timedelta(days=7)

    intervals = transport.query_free_busy(
        calendar_id="primary", time_min=time_min, time_max=time_max
    )

    assert intervals == [
        (datetime(2026, 5, 4, 1, tzinfo=UTC), datetime(2026, 5, 4, 3, tzinfo=UTC))
    ]
    # The query carried the window + calendar id; it reads ranges, not content.
    body = service.queries[0]
    assert body["items"] == [{"id": "primary"}]
    assert body["timeMin"] == time_min.isoformat()


def test_query_free_busy_empty_when_no_busy() -> None:
    transport = GoogleApiHttpTransport(
        _FakeFreeBusyService({"calendars": {"primary": {"busy": []}}})
    )
    t0 = datetime(2026, 5, 4, tzinfo=UTC)
    assert (
        transport.query_free_busy(
            calendar_id="primary", time_min=t0, time_max=t0 + timedelta(days=1)
        )
        == []
    )
