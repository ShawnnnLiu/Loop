"""Typed state and signal enums for the deterministic Supervisor.

Source: ``docs/axioms/02-state-machine.md``. Phase 1 implements the planning
subset (Strategist → Planner → Scheduler → AwaitingApproval). Calendar
write-back states arrive in Phase 2; we still declare them here so the
transition table is complete and a future change is additive only.
"""

from __future__ import annotations

from enum import StrEnum


class SupervisorState(StrEnum):
    """Every state the Supervisor can be in."""

    INITIAL = "initial"
    COLLECTING_USER_PROFILE = "collecting_user_profile"
    STRATEGIST_RUNNING = "strategist_running"
    STRATEGIST_VALIDATING = "strategist_validating"
    PLANNER_RUNNING = "planner_running"
    PLANNER_VALIDATING = "planner_validating"
    SCHEDULER_RUNNING = "scheduler_running"
    AWAITING_USER_APPROVAL = "awaiting_user_approval"
    WRITING_TO_CALENDAR = "writing_to_calendar"
    ERROR_REQUIRES_USER = "error_requires_user"
    TERMINAL_SUCCESS = "terminal_success"
    TERMINAL_DISCARDED = "terminal_discarded"


class SupervisorSignal(StrEnum):
    """Typed signal that a node emits after it runs.

    The Supervisor consumes the (state, signal) pair and returns the next
    state. Signals are emitted only by deterministic code; an LLM never
    chooses a signal.
    """

    USER_PROFILE_COLLECTED = "user_profile_collected"
    STRATEGIST_OUTPUT_PRODUCED = "strategist_output_produced"
    VALIDATION_PASSED = "validation_passed"
    VALIDATION_FAILED_REPAIRABLE = "validation_failed_repairable"
    REPAIR_LIMIT_EXCEEDED = "repair_limit_exceeded"
    PLANNER_OUTPUT_PRODUCED = "planner_output_produced"
    SCHEDULER_SUCCESS = "scheduler_success"
    SCHEDULER_PARTIAL_FAILURE = "scheduler_partial_failure"
    SCHEDULER_FULL_FAILURE = "scheduler_full_failure"
    USER_APPROVED = "user_approved"
    USER_REJECTED = "user_rejected"
    CALENDAR_WRITE_SUCCEEDED = "calendar_write_succeeded"
    CALENDAR_WRITE_FAILED = "calendar_write_failed"
    UNRECOVERABLE_ERROR = "unrecoverable_error"
