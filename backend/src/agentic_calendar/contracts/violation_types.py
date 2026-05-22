"""Typed ``ViolationType`` enum used inside ``validation_result.violations[]``.

Where ``ReasonCode`` answers "why did this artifact fail overall?",
``ViolationType`` answers "which specific check failed?". Each violation
carries supporting fields (``task_id``, ``module_id``, etc.) attached to the
``Violation`` model in ``validation_result.py``.

Source: ``docs/axioms/04-validation-layer.md`` (table of violation types and
user-facing translations) and ``docs/specs/validation-result.schema.md``.
"""

from __future__ import annotations

from enum import StrEnum


class ViolationType(StrEnum):
    """Specific structured failures produced by validation checkers."""

    # --- Schema-shape failures ---
    REQUIRED_FIELD_MISSING = "required_field_missing"
    FIELD_TYPE_INVALID = "field_type_invalid"
    ENUM_VALUE_INVALID = "enum_value_invalid"
    NUMERIC_OUT_OF_RANGE = "numeric_out_of_range"
    FORBIDDEN_FIELD_PRESENT = "forbidden_field_present"

    # --- Graph integrity ---
    DUPLICATE_TASK_ID = "duplicate_task_id"
    ORPHAN_DEPENDENCY = "orphan_dependency"
    CYCLE_DETECTED = "cycle_detected"
    SELF_DEPENDENCY = "self_dependency"
    MISSING_MODULE_ID = "missing_module_id"

    # --- Coverage ---
    MODULE_COVERAGE_MISSING = "module_coverage_missing"
    LOW_PRIORITY_MODULE_OVERWEIGHTED = "low_priority_module_overweighted"

    # --- User-fit ---
    DURATION_EXCEEDS_USER_MAX_SESSION = "duration_exceeds_user_max_session"
    DURATION_FAR_FROM_PREFERRED = "duration_far_from_preferred"
    WEEKLY_LOAD_EXCEEDS_CAPACITY = "weekly_load_exceeds_capacity"
    COGNITIVE_LOAD_OUT_OF_RANGE = "cognitive_load_out_of_range"
    CATEGORY_INVALID = "category_invalid"
    FOCUS_LEVEL_INVALID = "focus_level_invalid"
    HIGH_LOAD_TASKS_NOT_DISTRIBUTED = "high_load_tasks_not_distributed"

    # --- Scheduling preconditions ---
    NO_ROOT_TASK = "no_root_task"
