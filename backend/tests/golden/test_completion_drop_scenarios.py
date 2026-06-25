"""Golden scenarios for completion/drop memory + advisory ordering.

Covers ``docs/golden-test-cases.md`` scenarios 26-29 (ADR-0008). Each test maps
1:1 to its English description and drives the deterministic cycle harness; the
per-phase tests in ``tests/app`` cover the same paths in finer detail.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import pytest

from agentic_calendar.app.cycle import DEFAULT_TARGET_CALENDAR_ID
from agentic_calendar.app.environment import AppEnvironment
from agentic_calendar.contracts.calendar_event_mapping import CalendarWriteStatus
from agentic_calendar.contracts.reason_codes import ReasonCode
from agentic_calendar.contracts.task_disposition import (
    DispositionSource,
    TaskDispositionRecord,
    TaskDispositionType,
)
from agentic_calendar.contracts.task_plan import TaskPlan
from agentic_calendar.scheduler.adjustment import DraftAdjustment
from agentic_calendar.supervisor.state import SupervisorState as S
from tests._fixture_loader import iter_valid
from tests.app.test_cycle import USER_ID, RecordingPlanner, make_service

_NOW = datetime(2026, 5, 4, 12, 0, tzinfo=UTC)


def _disposition(
    task_id: str, disposition: TaskDispositionType
) -> TaskDispositionRecord:
    dropped = disposition is TaskDispositionType.DROPPED
    return TaskDispositionRecord(
        disposition_id=f"disp_{USER_ID}_seed_{task_id}_{disposition.value}",
        user_id=USER_ID,
        plan_version="seed",
        task_id=task_id,
        disposition=disposition,
        reason_code=ReasonCode.TASK_DROPPED_BY_USER if dropped else None,
        source=DispositionSource.USER if dropped else DispositionSource.SYSTEM,
        created_at=_NOW,
    )


def _drag_dp2_before_dp1(env: AppEnvironment, draft_id: str) -> DraftAdjustment:
    """dp_002 back-to-back BEFORE dp_001: no overlap, in-hours; the only fault is
    ordering (dp_001 lands Mon 18:00, so 90m earlier = Mon 16:30)."""
    draft = env.state.get_draft(draft_id)
    assert draft is not None
    dp1 = next(e for e in draft.entries if e.task_id == "dp_001")
    dp2 = next(e for e in draft.entries if e.task_id == "dp_002")
    return DraftAdjustment(task_id="dp_002", start=dp1.start - (dp2.end - dp2.start))


def test_scenario_26_manual_move_before_unfinished_prereq_is_advisory() -> None:
    service, env, _clock = make_service()
    proposed = service.propose(USER_ID)
    result = service.adjust(
        USER_ID, [_drag_dp2_before_dp1(env, proposed.draft_schedule_id)]
    )
    assert result.applied is True
    assert result.reason_code is None
    assert [w.reason_code for w in result.warnings] == [ReasonCode.DEPENDENCY_ADVISORY]
    assert result.state is S.AWAITING_USER_APPROVAL  # re-approval, not silent mutation


def test_scenario_27_completion_respected_suppresses_advisory() -> None:
    service, env, _clock = make_service()
    proposed = service.propose(USER_ID)
    env.disposition_store.append(_disposition("dp_001", TaskDispositionType.COMPLETED))
    result = service.adjust(
        USER_ID, [_drag_dp2_before_dp1(env, proposed.draft_schedule_id)]
    )
    assert result.applied is True
    assert result.warnings == []  # a completed prerequisite never warns


def test_scenario_28_drop_task_with_downstream_dependent() -> None:
    service, env, _clock = make_service()
    service.propose(USER_ID)
    service.approve(USER_ID)
    service.write(USER_ID)
    dp1_event = env.mapping_store.list_for_task("dp_001")[-1].calendar_event_id

    service.drop_tasks(USER_ID, ["dp_001"])  # dp_002 depends on dp_001
    service.approve(USER_ID)
    written = service.write(USER_ID)

    assert written.state is S.ACTIVE_PLAN
    active = env.plan_store.get_active(USER_ID)
    assert active is not None
    assert {t.task_id for t in active.plan.tasks} == {"dp_002"}
    assert active.plan.tasks[0].dependencies == []  # dp_001 pruned from deps
    # The dropped task's event is removed; the survivor's is untouched.
    assert (
        env.write_manager.read_event(
            target_calendar_id=DEFAULT_TARGET_CALENDAR_ID, calendar_event_id=dp1_event
        )
        is None
    )
    assert (
        env.mapping_store.list_for_task("dp_001")[-1].calendar_write_status
        is CalendarWriteStatus.ROLLED_BACK
    )
    assert (
        env.mapping_store.list_for_task("dp_002")[-1].calendar_write_status
        is CalendarWriteStatus.VERIFIED
    )


def test_scenario_29_regen_does_not_resurrect_dropped(
    caplog: pytest.LogCaptureFixture,
) -> None:
    plan = TaskPlan.model_validate(next(iter_valid("task_plan")).payload)
    recording = RecordingPlanner(plan)
    service, env, _clock = make_service(planner=recording)
    env.disposition_store.append(_disposition("dp_001", TaskDispositionType.DROPPED))

    with caplog.at_level(logging.WARNING):
        result = service.propose(USER_ID)

    # Advisory exclusion only: regeneration is not blocked, but it is logged.
    assert result.state is S.AWAITING_USER_APPROVAL
    assert "dp_001" in recording.excluded[-1]
    assert "reproduced dropped task" in caplog.text
