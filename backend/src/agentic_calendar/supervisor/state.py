"""Typed state and signal enums for the deterministic Supervisor.

Source: ``docs/axioms/02-state-machine.md``. Phase 1 implements the planning
subset (Strategist → Planner → Scheduler → AwaitingApproval). Phase 2 adds
the calendar write-back states declared below: ``CALENDAR_WRITE_APPROVED``,
``CALENDAR_WRITE_IN_PROGRESS``, ``CALENDAR_WRITE_VERIFIED``, and
``CALENDAR_WRITE_FAILED_STATE`` (the trailing ``_STATE`` disambiguates from
the ``CALENDAR_WRITE_FAILED`` signal that drives the transition into it).
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
    CALENDAR_WRITE_APPROVED = "calendar_write_approved"
    CALENDAR_WRITE_IN_PROGRESS = "calendar_write_in_progress"
    CALENDAR_WRITE_VERIFIED = "calendar_write_verified"
    CALENDAR_WRITE_FAILED_STATE = "calendar_write_failed"
    # Phase 4 (axiom 07): the post-write lifecycle. A verified write activates
    # the plan; telemetry-driven drift may then route a replan back through the
    # planner → validation → scheduler → approval pipeline (never a direct
    # calendar write — that invalid edge is absent from TRANSITIONS).
    ACTIVE_PLAN = "active_plan"
    DRIFT_DETECTED = "drift_detected"
    REPLAN_REQUIRED = "replan_required"
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
    DROP_REQUESTED = "drop_requested"
    """A user-initiated drop produced a survivors-only draft; route a fresh run
    straight to ``AWAITING_USER_APPROVAL`` (no scheduler — survivors keep their
    placements; completion/drop memory). The drop still passes the approval +
    (delete-only) write gate — no silent calendar write."""
    CALENDAR_WRITE_STARTED = "calendar_write_started"
    CALENDAR_WRITE_SUCCEEDED = "calendar_write_succeeded"
    CALENDAR_WRITE_FAILED = "calendar_write_failed"
    CALENDAR_VERIFICATION_FAILED = "calendar_verification_failed"
    CALENDAR_ROLLBACK_REQUESTED = "calendar_rollback_requested"
    CALENDAR_ROLLBACK_COMPLETED = "calendar_rollback_completed"

    # --- Active-plan / drift / replan loop (Phase 4, axiom 07) ---
    # The drift classifier is deterministic; the caller emits DRIFT_DETECTED
    # when classification returns at least one event, else NO_DRIFT. As with
    # CALENDAR_WRITE_FAILED, DRIFT_DETECTED / REPLAN_REQUIRED share a string
    # value with the like-named *state* — they live in different enums and the
    # routing table keys on the (state, signal) pair, so there is no collision.
    PLAN_ACTIVATED = "plan_activated"
    PLAN_COMPLETED = "plan_completed"
    DRIFT_DETECTED = "drift_detected"
    NO_DRIFT = "no_drift"
    REPLAN_REQUIRED = "replan_required"
    REPLAN_NOT_REQUIRED = "replan_not_required"
    REPLAN_STARTED = "replan_started"

    UNRECOVERABLE_ERROR = "unrecoverable_error"
