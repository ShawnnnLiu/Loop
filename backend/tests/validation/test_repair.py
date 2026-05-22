"""Tests for ``validation.repair.RepairPayload`` and ``next_action_for``."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from agentic_calendar.contracts.validation_result import (
    MAX_REPAIR_ATTEMPTS_LLM,
    ArtifactType,
    NextAction,
    Violation,
)
from agentic_calendar.contracts.violation_types import ViolationType
from agentic_calendar.validation.repair import RepairPayload, next_action_for


def test_repair_payload_requires_violations() -> None:
    with pytest.raises(ValidationError):
        RepairPayload(
            artifact_type=ArtifactType.TASK_PLAN,
            attempt=1,
            violations=[],
        )


def test_repair_payload_attempt_capped() -> None:
    with pytest.raises(ValidationError):
        RepairPayload(
            artifact_type=ArtifactType.TASK_PLAN,
            attempt=MAX_REPAIR_ATTEMPTS_LLM + 1,
            violations=[Violation(type=ViolationType.CYCLE_DETECTED)],
        )


def test_next_action_success() -> None:
    assert (
        next_action_for(valid=True, repair_attempt=0, repairable=False)
        is NextAction.SCHEDULER
    )


def test_next_action_first_failure_is_repair() -> None:
    assert (
        next_action_for(valid=False, repair_attempt=0, repairable=True)
        is NextAction.PLANNER_REPAIR_RETRY
    )


def test_next_action_at_cap_is_error_requires_user() -> None:
    assert (
        next_action_for(
            valid=False,
            repair_attempt=MAX_REPAIR_ATTEMPTS_LLM,
            repairable=True,
        )
        is NextAction.ERROR_REQUIRES_USER
    )


def test_next_action_unrepairable_is_error_requires_user() -> None:
    assert (
        next_action_for(valid=False, repair_attempt=0, repairable=False)
        is NextAction.ERROR_REQUIRES_USER
    )
