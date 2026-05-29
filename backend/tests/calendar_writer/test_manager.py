"""Tests for ``CalendarWriteManager`` (Phase 2)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from agentic_calendar.approval.store import InMemoryApprovalEventStore
from agentic_calendar.calendar_writer.in_memory_adapter import (
    FailureModes,
    InMemoryCalendarAdapter,
)
from agentic_calendar.calendar_writer.lock import CalendarWriteLockManager
from agentic_calendar.calendar_writer.manager import (
    CalendarWriteManager,
    WriteStatus,
)
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

_NOW = datetime(2026, 5, 4, 17, 55, tzinfo=UTC)


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
    expires_at: datetime | None = None,
    algorithm: HashAlgorithm = HashAlgorithm.SHA256,
    canonicalization_version: str = "v1",
    override_hash: str | None = None,
) -> ApprovalEvent:
    return ApprovalEvent(
        approval_event_id=approval_event_id,
        user_id=user_id,
        plan_id=draft.plan_version,
        draft_schedule_id=draft.draft_schedule_id,
        action_type=ApprovalActionType.ADD_TO_CALENDAR,
        approved_payload_hash=override_hash
        or canonical_payload_hash(draft, canonicalization_version),
        hash_algorithm=algorithm,
        hash_canonicalization_version=canonicalization_version,
        created_at=_NOW,
        expires_at=expires_at or (_NOW + timedelta(hours=24)),
    )


def _make_manager(
    *,
    failure_modes: FailureModes | None = None,
    clock: FrozenClock | None = None,
) -> tuple[
    CalendarWriteManager,
    InMemoryCalendarAdapter,
    InMemoryCalendarEventMappingStore,
    InMemoryApprovalEventStore,
    CalendarWriteLockManager,
    FrozenClock,
]:
    clk = clock or FrozenClock(_NOW)
    id_gen = DeterministicIdGenerator()
    adapter = InMemoryCalendarAdapter(id_generator=id_gen, failure_modes=failure_modes)
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
    return mgr, adapter, mapping_store, approval_store, lock, clk


# --------------------------------------------------------------------------- #
# preview
# --------------------------------------------------------------------------- #


def test_preview_returns_hash_and_planned_events() -> None:
    mgr, adapter, *_ = _make_manager()
    draft = _draft()
    result = mgr.preview(draft=draft, target_calendar_id="primary")
    assert result.draft_payload_hash == canonical_payload_hash(draft, "v1")
    assert len(result.planned_events) == 2
    assert {pe.task_id for pe in result.planned_events} == {"t1", "t2"}
    # preview must never call the adapter.
    assert adapter.all_events() == []


def test_preview_metadata_uses_app_tag_and_canonical_keys() -> None:
    mgr, *_ = _make_manager()
    result = mgr.preview(draft=_draft(), target_calendar_id="primary")
    for pe in result.planned_events:
        assert set(pe.metadata.keys()) == {"app", "run_id", "plan_version", "task_id"}
        assert pe.metadata["app"] == "career_scheduler"


# --------------------------------------------------------------------------- #
# approve_and_write — happy path
# --------------------------------------------------------------------------- #


def test_approve_and_write_success() -> None:
    mgr, adapter, mapping_store, approval_store, *_ = _make_manager()
    draft = _draft()
    approval = _approval_for(draft)
    approval_store.save(approval)

    result = mgr.approve_and_write(
        approval_event_id=approval.approval_event_id,
        draft=draft,
        target_calendar_id="primary",
    )
    assert result.status is WriteStatus.SUCCESS
    assert result.reason_code is None
    assert result.run_id is not None
    assert result.verification is not None
    assert result.verification.all_verified
    # All mappings end VERIFIED.
    for m in mapping_store.list_for_run(result.run_id):
        assert m.calendar_write_status is CalendarWriteStatus.VERIFIED
    # External events exist.
    assert len(adapter.all_events()) == 2


# --------------------------------------------------------------------------- #
# approve_and_write — pre-write aborts (no adapter call)
# --------------------------------------------------------------------------- #


def test_approve_and_write_missing_approval() -> None:
    mgr, adapter, mapping_store, *_ = _make_manager()
    draft = _draft()
    result = mgr.approve_and_write(
        approval_event_id="does_not_exist",
        draft=draft,
        target_calendar_id="primary",
    )
    assert result.status is WriteStatus.ABORTED_PRE_WRITE
    assert result.reason_code is ReasonCode.APPROVAL_MISSING
    assert result.run_id is None
    assert result.written_mappings == ()
    # Adapter was never touched.
    assert adapter.all_events() == []
    assert mapping_store.list_for_run("any") == []


def test_approve_and_write_expired_approval() -> None:
    mgr, adapter, _mapping_store, approval_store, _lock, clock = _make_manager()
    draft = _draft()
    approval = _approval_for(draft, expires_at=_NOW + timedelta(minutes=1))
    approval_store.save(approval)
    clock.advance(minutes=120)  # past expiry
    result = mgr.approve_and_write(
        approval_event_id=approval.approval_event_id,
        draft=draft,
        target_calendar_id="primary",
    )
    assert result.reason_code is ReasonCode.APPROVAL_EXPIRED
    assert result.status is WriteStatus.ABORTED_PRE_WRITE
    assert adapter.all_events() == []


def test_approve_and_write_hash_mismatch_aborts_before_adapter() -> None:
    """**P1**: a hash mismatch must NEVER call the adapter (axiom 06 line 208)."""
    mgr, adapter, _mapping_store, approval_store, *_ = _make_manager()
    draft = _draft()
    approval = _approval_for(
        draft,
        override_hash="sha256:" + ("0" * 64),  # bogus hash
    )
    approval_store.save(approval)
    result = mgr.approve_and_write(
        approval_event_id=approval.approval_event_id,
        draft=draft,
        target_calendar_id="primary",
    )
    assert result.reason_code is ReasonCode.APPROVAL_HASH_MISMATCH
    assert result.status is WriteStatus.ABORTED_PRE_WRITE
    assert adapter.all_events() == []


def test_approve_and_write_duplicate_detected_aborts_pre_write() -> None:
    """Pre-write metadata query finds an in-flight event tagged with the same
    run_id (axiom 06 lines 120-122) → ABORTED_PRE_WRITE with
    CALENDAR_WRITE_DUPLICATE_DETECTED. No further adapter writes happen.
    """
    mgr, adapter, mapping_store, approval_store, *_ = _make_manager()
    draft = _draft()
    approval = _approval_for(draft)
    approval_store.save(approval)

    # DeterministicIdGenerator emits "run_001" on the first new_id("run") call,
    # which is what approve_and_write will use. Pre-stage an event tagged with
    # that run_id to simulate a previous in-flight write the duplicate guard
    # must catch.
    adapter.create_event(
        target_calendar_id="primary",
        scheduled_start=datetime(2026, 5, 4, 18, 0, tzinfo=UTC),
        scheduled_end=datetime(2026, 5, 4, 19, 0, tzinfo=UTC),
        metadata={
            "app": "career_scheduler",
            "run_id": "run_001",
            "plan_version": draft.plan_version,
            "task_id": "t1",
        },
    )
    pre_write_event_count = len(adapter.all_events())

    result = mgr.approve_and_write(
        approval_event_id=approval.approval_event_id,
        draft=draft,
        target_calendar_id="primary",
    )
    assert result.status is WriteStatus.ABORTED_PRE_WRITE
    assert result.reason_code is ReasonCode.CALENDAR_WRITE_DUPLICATE_DETECTED
    assert result.run_id == "run_001"
    assert result.written_mappings == ()
    # No new events created; the pre-staged event is the only one present.
    assert len(adapter.all_events()) == pre_write_event_count
    # No mappings persisted under the colliding run_id.
    assert mapping_store.list_for_run("run_001") == []


def test_approve_and_write_unsupported_canonicalization_version() -> None:
    mgr, adapter, _mapping_store, approval_store, *_ = _make_manager()
    draft = _draft()
    # Use a valid hash but an unknown canonicalization version.
    approval = ApprovalEvent(
        approval_event_id="approval_001",
        user_id="user_a",
        plan_id=draft.plan_version,
        draft_schedule_id=draft.draft_schedule_id,
        action_type=ApprovalActionType.ADD_TO_CALENDAR,
        approved_payload_hash="sha256:" + ("a" * 64),
        hash_algorithm=HashAlgorithm.SHA256,
        hash_canonicalization_version="v999",  # unknown
        created_at=_NOW,
        expires_at=_NOW + timedelta(hours=24),
    )
    approval_store.save(approval)
    result = mgr.approve_and_write(
        approval_event_id=approval.approval_event_id,
        draft=draft,
        target_calendar_id="primary",
    )
    assert result.reason_code is ReasonCode.APPROVAL_HASH_ALGORITHM_UNSUPPORTED
    assert adapter.all_events() == []


# --------------------------------------------------------------------------- #
# approve_and_write — lock contention
# --------------------------------------------------------------------------- #


def test_approve_and_write_lock_busy() -> None:
    mgr, _adapter, _ms, approval_store, lock, _ = _make_manager()
    draft = _draft()
    approval = _approval_for(draft)
    approval_store.save(approval)
    # Pre-acquire the lock for the same user.
    lock.acquire(user_id="user_a", run_id="someone_else")
    result = mgr.approve_and_write(
        approval_event_id=approval.approval_event_id,
        draft=draft,
        target_calendar_id="primary",
    )
    assert result.status is WriteStatus.LOCK_BUSY
    assert result.reason_code is ReasonCode.CALENDAR_WRITE_LOCK_BUSY


# --------------------------------------------------------------------------- #
# approve_and_write — partial failure
# --------------------------------------------------------------------------- #


def test_approve_and_write_partial_failure_drop_silent() -> None:
    mgr, _adapter, mapping_store, approval_store, *_ = _make_manager(
        failure_modes=FailureModes(drop_silently_for_task_ids=frozenset({"t1"}))
    )
    draft = _draft()
    approval = _approval_for(draft)
    approval_store.save(approval)
    result = mgr.approve_and_write(
        approval_event_id=approval.approval_event_id,
        draft=draft,
        target_calendar_id="primary",
    )
    assert result.status is WriteStatus.PARTIAL_FAILURE
    assert result.reason_code is ReasonCode.EXTERNAL_SYNC_FAILED
    assert result.run_id is not None
    # t1 mapping is marked VERIFICATION_FAILED; t2 is VERIFIED.
    by_task = {
        m.task_id: m.calendar_write_status
        for m in mapping_store.list_for_run(result.run_id)
    }
    assert by_task["t1"] is CalendarWriteStatus.VERIFICATION_FAILED
    assert by_task["t2"] is CalendarWriteStatus.VERIFIED


def test_approve_and_write_create_failure_marks_write_failed() -> None:
    mgr, _adapter, _mapping_store, approval_store, *_ = _make_manager(
        failure_modes=FailureModes(fail_create_for_task_ids=frozenset({"t1"}))
    )
    draft = _draft()
    approval = _approval_for(draft)
    approval_store.save(approval)
    result = mgr.approve_and_write(
        approval_event_id=approval.approval_event_id,
        draft=draft,
        target_calendar_id="primary",
    )
    assert result.status is WriteStatus.PARTIAL_FAILURE
    assert result.reason_code is ReasonCode.CALENDAR_WRITE_FAILED


# --------------------------------------------------------------------------- #
# verify
# --------------------------------------------------------------------------- #


def test_verify_after_success_returns_all_verified() -> None:
    mgr, _adapter, _ms, approval_store, *_ = _make_manager()
    draft = _draft()
    approval = _approval_for(draft)
    approval_store.save(approval)
    write_result = mgr.approve_and_write(
        approval_event_id=approval.approval_event_id,
        draft=draft,
        target_calendar_id="primary",
    )
    assert write_result.run_id is not None
    verification = mgr.verify(
        run_id=write_result.run_id, target_calendar_id="primary"
    )
    assert verification.all_verified


# --------------------------------------------------------------------------- #
# rollback
# --------------------------------------------------------------------------- #


def test_rollback_after_success_marks_mappings_rolled_back() -> None:
    """Rolling back a fully-VERIFIED run deletes every external event and
    transitions every mapping to ROLLED_BACK (axiom 06 lines 132-137)."""
    mgr, adapter, mapping_store, approval_store, *_ = _make_manager()
    draft = _draft()
    approval = _approval_for(draft)
    approval_store.save(approval)
    write_result = mgr.approve_and_write(
        approval_event_id=approval.approval_event_id,
        draft=draft,
        target_calendar_id="primary",
    )
    assert write_result.run_id is not None
    # All mappings start VERIFIED after a successful write.
    for m in mapping_store.list_for_run(write_result.run_id):
        assert m.calendar_write_status is CalendarWriteStatus.VERIFIED

    rollback = mgr.rollback(
        run_id=write_result.run_id, target_calendar_id="primary"
    )
    assert rollback.fully_rolled_back
    for m in mapping_store.list_for_run(write_result.run_id):
        assert m.calendar_write_status is CalendarWriteStatus.ROLLED_BACK
    assert adapter.all_events() == []


def test_rollback_with_failing_delete_marks_rollback_failed() -> None:
    mgr, adapter, mapping_store, approval_store, *_ = _make_manager()
    draft = _draft()
    approval = _approval_for(draft)
    approval_store.save(approval)
    write_result = mgr.approve_and_write(
        approval_event_id=approval.approval_event_id,
        draft=draft,
        target_calendar_id="primary",
    )
    assert write_result.run_id is not None
    # Inject delete failure for one event.
    failing_id = mapping_store.list_for_run(write_result.run_id)[0].calendar_event_id
    assert failing_id is not None
    adapter._failure_modes = FailureModes(  # type: ignore[attr-defined]
        fail_delete_for_event_ids=frozenset({failing_id})
    )

    rollback = mgr.rollback(
        run_id=write_result.run_id, target_calendar_id="primary"
    )
    assert not rollback.fully_rolled_back
    assert rollback.reason_code is ReasonCode.CALENDAR_ROLLBACK_FAILED
    statuses = {
        m.task_id: m.calendar_write_status
        for m in mapping_store.list_for_run(write_result.run_id)
    }
    # One failed, one succeeded.
    assert CalendarWriteStatus.ROLLBACK_FAILED in statuses.values()
    assert CalendarWriteStatus.ROLLED_BACK in statuses.values()


# --------------------------------------------------------------------------- #
# reconcile_after_crash
# --------------------------------------------------------------------------- #


def test_reconcile_writes_only_missing_tasks() -> None:
    """After a partial-failure write, reconcile only writes the missing event."""
    mgr, adapter, mapping_store, approval_store, *_ = _make_manager(
        failure_modes=FailureModes(drop_silently_for_task_ids=frozenset({"t1"}))
    )
    draft = _draft()
    approval = _approval_for(draft)
    approval_store.save(approval)
    write_result = mgr.approve_and_write(
        approval_event_id=approval.approval_event_id,
        draft=draft,
        target_calendar_id="primary",
    )
    assert write_result.run_id is not None
    assert write_result.status is WriteStatus.PARTIAL_FAILURE

    # Clear failure modes; reconcile should now succeed for t1.
    adapter._failure_modes = FailureModes()  # type: ignore[attr-defined]
    reconcile_result = mgr.reconcile_after_crash(
        approval_event_id=approval.approval_event_id,
        draft=draft,
        run_id=write_result.run_id,
        target_calendar_id="primary",
    )
    assert reconcile_result.status is WriteStatus.SUCCESS
    # All mappings end VERIFIED.
    for m in mapping_store.list_for_run(write_result.run_id):
        assert m.calendar_write_status is CalendarWriteStatus.VERIFIED


def test_reconcile_rejects_mismatched_draft_hash() -> None:
    """Per axiom 06 lines 181-189 the hash recheck is MANDATORY on every
    write path — reconcile cannot quietly write the original payload if the
    draft has changed since approval. Passing a draft whose canonical hash
    differs from the approval's recorded hash must abort with
    APPROVAL_HASH_MISMATCH before any adapter call."""
    mgr, adapter, _ms, approval_store, *_ = _make_manager(
        failure_modes=FailureModes(drop_silently_for_task_ids=frozenset({"t1"}))
    )
    original_draft = _draft()
    approval = _approval_for(original_draft)
    approval_store.save(approval)
    write_result = mgr.approve_and_write(
        approval_event_id=approval.approval_event_id,
        draft=original_draft,
        target_calendar_id="primary",
    )
    assert write_result.run_id is not None
    assert write_result.status is WriteStatus.PARTIAL_FAILURE

    # The draft was mutated between approval and reconcile (a different
    # task list with the same plan_version/draft_schedule_id).
    mutated_draft = _draft(
        entries=(
            DraftScheduleEntry(
                task_id="t_NEW",
                start=datetime(2026, 5, 4, 22, 0, tzinfo=UTC),
                end=datetime(2026, 5, 4, 23, 0, tzinfo=UTC),
            ),
        )
    )
    adapter._failure_modes = FailureModes()  # type: ignore[attr-defined]
    events_before = len(adapter.all_events())
    result = mgr.reconcile_after_crash(
        approval_event_id=approval.approval_event_id,
        draft=mutated_draft,
        run_id=write_result.run_id,
        target_calendar_id="primary",
    )
    assert result.status is WriteStatus.ABORTED_PRE_WRITE
    assert result.reason_code is ReasonCode.APPROVAL_HASH_MISMATCH
    # run_id is preserved on the failure result for telemetry.
    assert result.run_id == write_result.run_id
    # No further adapter writes happened.
    assert len(adapter.all_events()) == events_before


def test_reconcile_lock_busy() -> None:
    mgr, _adapter, _ms, approval_store, lock, _ = _make_manager()
    draft = _draft()
    approval = _approval_for(draft)
    approval_store.save(approval)
    write_result = mgr.approve_and_write(
        approval_event_id=approval.approval_event_id,
        draft=draft,
        target_calendar_id="primary",
    )
    assert write_result.run_id is not None
    # Acquire the lock for the same user with a different run.
    lock.acquire(user_id="user_a", run_id="someone_else")
    result = mgr.reconcile_after_crash(
        approval_event_id=approval.approval_event_id,
        draft=draft,
        run_id=write_result.run_id,
        target_calendar_id="primary",
    )
    assert result.status is WriteStatus.LOCK_BUSY
    assert result.reason_code is ReasonCode.CALENDAR_WRITE_LOCK_BUSY


# --------------------------------------------------------------------------- #
# misc: lock is released after success
# --------------------------------------------------------------------------- #


def test_lock_released_after_success_so_re_run_is_possible() -> None:
    mgr, _adapter, _ms, approval_store, lock, _ = _make_manager()
    draft = _draft()
    approval = _approval_for(draft)
    approval_store.save(approval)
    mgr.approve_and_write(
        approval_event_id=approval.approval_event_id,
        draft=draft,
        target_calendar_id="primary",
    )
    # Lock should be released; new acquire by same user must work.
    token = lock.acquire(user_id="user_a", run_id="new_run")
    assert token.holder_run_id == "new_run"


def test_lock_released_on_pre_write_abort() -> None:
    mgr, _adapter, _ms, _approval_store, lock, _ = _make_manager()
    mgr.approve_and_write(
        approval_event_id="missing",
        draft=_draft(),
        target_calendar_id="primary",
    )
    # No lock was ever acquired (abort happened before lock step).
    token = lock.acquire(user_id="user_a", run_id="r")
    assert token.holder_run_id == "r"




