"""Tests for the scheduler's exception-translation boundary (axiom 16).

``schedule()`` must never let a raw exception leave the region: every
internal ``SchedulerError`` is translated into a schema-valid
``schedule_status="failed"`` output with one typed ``UnscheduledTask`` per
plan task.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from agentic_calendar.contracts.reason_codes import ReasonCode
from agentic_calendar.contracts.scheduler_output import ScheduleStatus
from agentic_calendar.scheduler.errors import (
    HorizonNotTimezoneAwareError,
    SchedulerError,
)
from agentic_calendar.scheduler.greedy import schedule
from agentic_calendar.scheduler.inputs import SchedulerInput
from agentic_calendar.scheduler.windows import enumerate_free_windows
from tests.scheduler._helpers import DEFAULT_POLICY, make_input, make_plan, make_task


def _naive_horizon_input() -> SchedulerInput:
    """A ``SchedulerInput`` with a naive horizon, bypassing the contract.

    ``SchedulerInput`` itself rejects naive horizons, so ``model_construct``
    simulates the only way one can reach the placement loop: a caller that
    bypassed validation. The boundary must still translate, not raise.
    """
    valid = make_input(make_plan(make_task(task_id="a"), make_task(task_id="b")))
    return SchedulerInput.model_construct(
        run_id=valid.run_id,
        plan_version=valid.plan_version,
        plan=valid.plan,
        policy=valid.policy,
        calendar_free_busy=list(valid.calendar_free_busy),
        completed_task_ids=list(valid.completed_task_ids),
        horizon_start=datetime(2026, 5, 4, 0, 0, 0),
        horizon_end=datetime(2026, 5, 7, 0, 0, 0),
    )


def test_enumerate_free_windows_raises_typed_error_for_naive_horizon() -> None:
    naive = datetime(2026, 5, 4, 0, 0, 0)
    with pytest.raises(HorizonNotTimezoneAwareError):
        enumerate_free_windows(
            horizon_start=naive,
            horizon_end=naive + timedelta(days=1),
            free_busy=[],
            policy=DEFAULT_POLICY,
        )


def test_horizon_error_is_a_scheduler_error_with_typed_reason_code() -> None:
    assert issubclass(HorizonNotTimezoneAwareError, SchedulerError)
    assert (
        HorizonNotTimezoneAwareError.reason_code
        is ReasonCode.SCHEDULING_PRECONDITION_FAILED
    )


def test_schedule_translates_internal_error_to_failed_output() -> None:
    out = schedule(_naive_horizon_input())

    assert out.schedule_status is ScheduleStatus.FAILED
    assert out.scheduled_tasks == []
    assert {u.task_id for u in out.unscheduled_tasks} == {"a", "b"}
    for u in out.unscheduled_tasks:
        assert u.reason_code is ReasonCode.SCHEDULING_PRECONDITION_FAILED
        assert u.debug["error_type"] == "HorizonNotTimezoneAwareError"
        assert u.debug["detail"]
    assert out.repair_options  # non-success outputs must offer repair options
    assert out.run_id == "run_test"
    assert out.plan_version == "plan_test"


def test_schedule_never_raises_on_aware_input() -> None:
    # The happy path stays untouched by the boundary wrapper.
    out = schedule(make_input(make_plan(make_task(task_id="a"))))
    assert out.schedule_status is ScheduleStatus.SUCCESS
    assert len(out.scheduled_tasks) == 1
    assert out.scheduled_tasks[0].start.tzinfo is not None
