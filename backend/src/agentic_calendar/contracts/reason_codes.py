"""Typed ``ReasonCode`` enum (cross-cutting).

Every failure in the system carries a ``ReasonCode``. The enum is the single
source of truth used by validation, the scheduler, the supervisor, telemetry
(later phases), and user-facing explanations (axiom 16).

Add new codes here when a new failure mode appears; the type checker will
then surface every site that must handle them. Phase 1 covers the codes
needed by the planning core; calendar/telemetry/sponsor codes will be added
in their respective phases.

Sources:
    * ``docs/axioms/04-validation-layer.md`` (validation / repair codes)
    * ``docs/axioms/05-scheduler-policy.md`` (scheduler codes)
    * ``docs/axioms/12-edge-case-policy-engine.md`` (policy codes)
    * ``docs/axioms/15-plan-versioning-and-diffs.md`` (diff reason codes; later)
    * ``docs/axioms/16-reliability-patterns.md`` (canonical list)
"""

from __future__ import annotations

from enum import StrEnum


class ReasonCode(StrEnum):
    """All typed failure / outcome codes in the system.

    Codes are uppercase ``SCREAMING_SNAKE_CASE`` strings so they survive a
    JSON round-trip unchanged and so they read identically in logs, telemetry,
    and user-facing explanations.
    """

    # --- Validation (axiom 04 + axiom 16) ---
    VALIDATION_FAILED = "VALIDATION_FAILED"
    """Generic validation failure; prefer a more specific code where possible."""

    SCHEMA_INVALID = "SCHEMA_INVALID"
    """Pydantic / shape validation failed (required field missing, bad enum, etc.)."""

    TASK_GRAPH_INVALID = "TASK_GRAPH_INVALID"
    """One or more graph-integrity checks failed (cycle, orphan, duplicate, self-dep)."""

    MODULE_COVERAGE_INSUFFICIENT = "MODULE_COVERAGE_INSUFFICIENT"
    """A required syllabus module has no tasks, or coverage is silently dropped."""

    USER_FIT_VIOLATED = "USER_FIT_VIOLATED"
    """Plan exceeds capacity, session length, or other profile-derived bounds."""

    SCHEDULING_PRECONDITION_FAILED = "SCHEDULING_PRECONDITION_FAILED"
    """The plan is not in a state the scheduler can consume."""

    REPAIR_LIMIT_EXCEEDED = "REPAIR_LIMIT_EXCEEDED"
    """Two failed repair attempts; route to ``error_requires_user``."""

    FORBIDDEN_FIELD_PRESENT = "FORBIDDEN_FIELD_PRESENT"
    """An LLM-produced artifact contained a field code is required to compute
    (e.g. ``task_plan.prerequisites_met``)."""

    # --- Scheduler (axiom 05) ---
    NO_VALID_CONTIGUOUS_BLOCK = "NO_VALID_CONTIGUOUS_BLOCK"
    INSUFFICIENT_WEEKLY_CAPACITY = "INSUFFICIENT_WEEKLY_CAPACITY"
    DEPENDENCY_BLOCKED = "DEPENDENCY_BLOCKED"
    OUTSIDE_ALLOWED_HOURS = "OUTSIDE_ALLOWED_HOURS"
    DAILY_LOAD_EXCEEDED = "DAILY_LOAD_EXCEEDED"
    DEEP_WORK_REQUIRED_UNAVAILABLE = "DEEP_WORK_REQUIRED_UNAVAILABLE"
    TASK_TOO_LONG_UNSPLITTABLE = "TASK_TOO_LONG_UNSPLITTABLE"
    TASK_TOO_LONG_SPLITTABLE = "TASK_TOO_LONG_SPLITTABLE"

    # --- Supervisor / state machine (axiom 02 + axiom 16) ---
    INVALID_STATE_TRANSITION = "INVALID_STATE_TRANSITION"
    USER_APPROVAL_REQUIRED = "USER_APPROVAL_REQUIRED"
    ERROR_REQUIRES_USER = "ERROR_REQUIRES_USER"

    # --- Profile / capacity changes (axiom 12) ---
    PROFILE_MAJOR_CHANGE = "PROFILE_MAJOR_CHANGE"
    CAPACITY_CHANGE = "CAPACITY_CHANGE"
