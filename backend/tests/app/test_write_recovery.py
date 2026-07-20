"""Write-failure recovery: user-triggered rollback and retry (UX pass B1).

A failed/unverified calendar write used to strand the run permanently in
``CALENDAR_WRITE_FAILED_STATE`` — the recovery primitives existed on
``CalendarWriteManager`` but nothing emitted the rollback signals and no retry
edge existed. These tests cover the two service paths end-to-end over the
in-memory adapter's supported failure modes:

* ``rollback``   — dry-run count, full rollback → ``ERROR_REQUIRES_USER``,
                   partial rollback → stays recoverable, retry-after-partial.
* ``retry_write`` — missing-events reconcile after a verification failure,
                   mid-write crash healing (including draft entries the
                   original write never attempted), and the fresh-write
                   fallback when nothing was ever written.
"""

from __future__ import annotations

import pytest

from agentic_calendar.app.cycle import CycleError
from agentic_calendar.calendar_writer.in_memory_adapter import (
    FailureModes,
    InMemoryCalendarAdapter,
)
from agentic_calendar.common.ids import DeterministicIdGenerator
from agentic_calendar.contracts.reason_codes import ReasonCode
from agentic_calendar.supervisor.state import SupervisorState as S
from tests.app.test_cycle import PLAN_TASK_IDS, USER_ID, make_service


def _failing_adapter(modes: FailureModes) -> InMemoryCalendarAdapter:
    return InMemoryCalendarAdapter(
        id_generator=DeterministicIdGenerator(), failure_modes=modes
    )


def _fail_write(service, adapter):  # type: ignore[no-untyped-def]
    """Propose → approve → write; assert the run parked in the failure state."""
    service.propose(USER_ID)
    service.approve(USER_ID)
    written = service.write(USER_ID)
    assert written.state is S.CALENDAR_WRITE_FAILED_STATE
    adapter.set_failure_modes(FailureModes())  # the external service "recovers"
    return written


# --------------------------------------------------------------------------- #
# rollback
# --------------------------------------------------------------------------- #


def test_rollback_dry_run_reports_count_without_deleting() -> None:
    adapter = _failing_adapter(
        FailureModes(corrupt_metadata_for_task_ids=frozenset({"dp_001"}))
    )
    service, env, _clock = make_service(calendar_adapter=adapter)
    _fail_write(service, adapter)

    result = service.rollback(USER_ID, dry_run=True)

    assert result.dry_run is True
    assert result.rollbackable_event_count == len(PLAN_TASK_IDS)
    assert result.state is S.CALENDAR_WRITE_FAILED_STATE  # nothing changed
    assert result.fully_rolled_back is None
    # The calendar still holds every event the failed write created.
    run = env.state.latest_run_for_user(USER_ID)
    assert run is not None and run.write_op_id is not None
    mappings = env.mapping_store.list_for_run(run.write_op_id)
    assert len(mappings) == len(PLAN_TASK_IDS)


def test_rollback_deletes_events_and_exits_to_error_requires_user() -> None:
    adapter = _failing_adapter(
        FailureModes(corrupt_metadata_for_task_ids=frozenset({"dp_001"}))
    )
    service, env, _clock = make_service(calendar_adapter=adapter)
    _fail_write(service, adapter)

    result = service.rollback(USER_ID)

    assert result.dry_run is False
    assert result.fully_rolled_back is True
    assert result.state is S.ERROR_REQUIRES_USER
    assert len(result.deleted_event_ids) == len(PLAN_TASK_IDS)
    assert result.failed_event_ids == []
    # The original write-failure reason survives for the resume surface.
    run = env.state.latest_run_for_user(USER_ID)
    assert run is not None
    assert run.state is S.ERROR_REQUIRES_USER
    assert run.reason_code is ReasonCode.EXTERNAL_SYNC_FAILED
    # No plan was ever activated.
    assert env.plan_store.get_active(USER_ID) is None


def test_partial_rollback_stays_recoverable_then_completes_on_retry() -> None:
    adapter = _failing_adapter(
        FailureModes(corrupt_metadata_for_task_ids=frozenset({"dp_001"}))
    )
    service, env, _clock = make_service(calendar_adapter=adapter)
    _fail_write(service, adapter)

    run = env.state.latest_run_for_user(USER_ID)
    assert run is not None and run.write_op_id is not None
    stuck_event_id = env.mapping_store.list_for_run(run.write_op_id)[0].calendar_event_id
    assert stuck_event_id is not None
    adapter.set_failure_modes(
        FailureModes(fail_delete_for_event_ids=frozenset({stuck_event_id}))
    )

    partial = service.rollback(USER_ID)
    assert partial.fully_rolled_back is False
    assert partial.state is S.CALENDAR_WRITE_FAILED_STATE  # still recoverable
    assert partial.reason_code is ReasonCode.CALENDAR_ROLLBACK_FAILED
    assert stuck_event_id in partial.failed_event_ids

    # The external service recovers; a second rollback finishes the job.
    adapter.set_failure_modes(FailureModes())
    finished = service.rollback(USER_ID)
    assert finished.fully_rolled_back is True
    assert finished.state is S.ERROR_REQUIRES_USER


def test_rollback_requires_the_failure_state() -> None:
    service, _env, _clock = make_service()
    service.propose(USER_ID)
    with pytest.raises(CycleError, match="requires 'calendar_write_failed'"):
        service.rollback(USER_ID)


# --------------------------------------------------------------------------- #
# retry_write
# --------------------------------------------------------------------------- #


def test_retry_after_verification_failure_recreates_missing_and_activates() -> None:
    """A silently dropped event fails verification; the retry re-creates ONLY
    the missing event (reconcile path) and the run reaches ACTIVE_PLAN."""
    adapter = _failing_adapter(
        FailureModes(drop_silently_for_task_ids=frozenset({"dp_001"}))
    )
    service, env, _clock = make_service(calendar_adapter=adapter)
    failed = _fail_write(service, adapter)
    assert failed.reason_code is ReasonCode.EXTERNAL_SYNC_FAILED

    result = service.retry_write(USER_ID)

    assert result.state is S.ACTIVE_PLAN
    assert result.reason_code is None
    # The retry reports the FULL planned draft, not just the events this pass
    # created — the live smoke rendered "2 / 0 verified" when planned stayed 0.
    assert result.planned_event_count == len(PLAN_TASK_IDS)
    assert sorted(result.verified_task_ids) == sorted(PLAN_TASK_IDS)
    assert env.plan_store.get_active(USER_ID) is not None


def test_retry_after_midwrite_crash_covers_unattempted_tasks() -> None:
    """dp_002's create raised mid-write, so it has NO mapping. The retry must
    create it anyway (the approved draft is the source of truth) — a reconcile
    that only heals mapped tasks would false-succeed with events missing."""
    adapter = _failing_adapter(
        FailureModes(fail_create_for_task_ids=frozenset({"dp_002"}))
    )
    service, env, _clock = make_service(calendar_adapter=adapter)
    failed = _fail_write(service, adapter)
    assert failed.reason_code is ReasonCode.CALENDAR_WRITE_FAILED

    result = service.retry_write(USER_ID)

    assert result.state is S.ACTIVE_PLAN
    assert sorted(result.verified_task_ids) == sorted(PLAN_TASK_IDS)
    run = env.state.latest_run_for_user(USER_ID)
    assert run is not None and run.write_op_id is not None
    mappings = env.mapping_store.list_for_run(run.write_op_id)
    assert sorted(m.task_id for m in mappings) == sorted(PLAN_TASK_IDS)


def test_retry_after_prewrite_abort_falls_back_to_full_write() -> None:
    """dp_001 is scheduled first, so failing its create aborts the write
    before any mapping exists. The retry takes the fresh approve_and_write
    path — a reconcile over zero mappings would no-op and falsely report
    success."""
    adapter = _failing_adapter(
        FailureModes(fail_create_for_task_ids=frozenset({"dp_001"}))
    )
    service, env, _clock = make_service(calendar_adapter=adapter)
    _fail_write(service, adapter)

    result = service.retry_write(USER_ID)

    assert result.state is S.ACTIVE_PLAN
    assert sorted(result.verified_task_ids) == sorted(PLAN_TASK_IDS)
    assert env.plan_store.get_active(USER_ID) is not None


def _expected_titles(env) -> dict[str, str]:  # type: ignore[no-untyped-def]
    """``task_id`` → real title from the run's plan version."""
    run = env.state.latest_run_for_user(USER_ID)
    assert run is not None and run.plan_version is not None
    plan = env.plan_store.get(USER_ID, run.plan_version)
    assert plan is not None
    return {task.task_id: task.title for task in plan.plan.tasks}


def test_retry_reconcile_recreates_events_with_real_titles() -> None:
    """The highest-risk silent regression: ``retry_write``'s reconcile path
    must carry the title map, or recreated events quietly revert to the
    generic summary with no error signal."""
    adapter = _failing_adapter(
        FailureModes(drop_silently_for_task_ids=frozenset({"dp_001"}))
    )
    service, env, _clock = make_service(calendar_adapter=adapter)
    _fail_write(service, adapter)

    result = service.retry_write(USER_ID)

    assert result.state is S.ACTIVE_PLAN
    titles = _expected_titles(env)
    events = adapter.all_events()
    assert sorted(e.metadata["task_id"] for e in events) == sorted(PLAN_TASK_IDS)
    for event in events:
        assert event.summary == titles[event.metadata["task_id"]]
        assert event.summary


def test_retry_fallback_full_write_carries_real_titles() -> None:
    """``retry_write``'s pre-write-abort fallback (fresh ``approve_and_write``)
    must carry the title map too — missing either call site regresses retried
    writes to the generic title."""
    adapter = _failing_adapter(
        FailureModes(fail_create_for_task_ids=frozenset({"dp_001"}))
    )
    service, env, _clock = make_service(calendar_adapter=adapter)
    _fail_write(service, adapter)

    result = service.retry_write(USER_ID)

    assert result.state is S.ACTIVE_PLAN
    titles = _expected_titles(env)
    events = adapter.all_events()
    assert sorted(e.metadata["task_id"] for e in events) == sorted(PLAN_TASK_IDS)
    for event in events:
        assert event.summary == titles[event.metadata["task_id"]]
        assert event.summary


def test_retry_write_requires_the_failure_state() -> None:
    service, _env, _clock = make_service()
    service.propose(USER_ID)
    with pytest.raises(CycleError, match="requires 'calendar_write_failed'"):
        service.retry_write(USER_ID)


def test_recovery_survives_restart_from_sqlite(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """write_op_id persists on the run record: a service rebuilt over the same
    SQLite file can still roll back the pre-restart failed write."""
    db_path = tmp_path / "state.db"
    adapter = _failing_adapter(
        FailureModes(corrupt_metadata_for_task_ids=frozenset({"dp_001"}))
    )
    service, _env, _clock = make_service(calendar_adapter=adapter, db_path=db_path)
    _fail_write(service, adapter)

    reopened, _env2, _clock2 = make_service(
        calendar_adapter=adapter, db_path=db_path, onboard=False, seed_claims=False
    )
    result = reopened.rollback(USER_ID, dry_run=True)
    assert result.rollbackable_event_count == len(PLAN_TASK_IDS)
