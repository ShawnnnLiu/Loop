"""Tests for ``SchedulerOutput`` and friends."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from agentic_calendar.contracts.scheduler_output import SchedulerOutput
from tests._fixture_loader import iter_invalid, iter_valid

CONTRACT = "scheduler_output"


@pytest.mark.parametrize(
    "fixture",
    list(iter_valid(CONTRACT)),
    ids=lambda f: f.name,
)
def test_valid_fixture_parses(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    out = SchedulerOutput.model_validate(payload)
    assert out.run_id == payload["run_id"]


@pytest.mark.parametrize(
    "fixture",
    list(iter_invalid(CONTRACT)),
    ids=lambda f: f.name,
)
def test_invalid_fixture_rejected(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    expected = fixture.expected  # type: ignore[attr-defined]
    with pytest.raises(ValidationError) as exc_info:
        SchedulerOutput.model_validate(payload)
    msg = str(exc_info.value)
    for substr in expected["error_substrings"]:
        assert substr in msg, (
            f"expected substring {substr!r} not in error message:\n{msg}"
        )


def test_success_with_unscheduled_rejected() -> None:
    payload = {
        "run_id": "r",
        "plan_version": "p",
        "schedule_status": "success",
        "scheduled_tasks": [],
        "unscheduled_tasks": [
            {
                "task_id": "t1",
                "reason_code": "NO_VALID_CONTIGUOUS_BLOCK",
                "debug": {"required_duration_min": 90},
            }
        ],
        "available_capacity_min": 0,
        "largest_available_block_min": 0,
        "repair_options": [],
    }
    with pytest.raises(ValidationError) as exc_info:
        SchedulerOutput.model_validate(payload)
    assert "success" in str(exc_info.value)
