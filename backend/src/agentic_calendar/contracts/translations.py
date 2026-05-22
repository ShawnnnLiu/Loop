"""Deterministic ``ViolationType`` → user-facing string table.

Source: ``docs/axioms/04-validation-layer.md`` ("User-Facing Violation
Translation"). The table is the authoritative single source of truth; the
``UserFacingExplanationNode`` may compose multi-violation summaries from
these strings, but it must not invent translations on the fly.
"""

from __future__ import annotations

from agentic_calendar.contracts.violation_types import ViolationType

USER_FACING: dict[ViolationType, str] = {
    ViolationType.ORPHAN_DEPENDENCY: (
        "A task referenced a prerequisite that doesn't exist. Fixing now."
    ),
    ViolationType.CYCLE_DETECTED: (
        "Two tasks depend on each other in a loop. Restructuring."
    ),
    ViolationType.SELF_DEPENDENCY: (
        "A task depended on itself. Removing the cycle."
    ),
    ViolationType.DUPLICATE_TASK_ID: (
        "Two tasks shared the same ID. Re-numbering."
    ),
    ViolationType.MISSING_MODULE_ID: (
        "A task referenced a module that doesn't exist. Re-aligning the plan."
    ),
    ViolationType.MODULE_COVERAGE_MISSING: (
        "An important module was missing tasks. Adding them."
    ),
    ViolationType.DURATION_EXCEEDS_USER_MAX_SESSION: (
        "A task was too long for your session preferences. Splitting it up."
    ),
    ViolationType.DURATION_FAR_FROM_PREFERRED: (
        "Some tasks were much shorter than your preferred session length, "
        "which can fragment focus. Re-sizing."
    ),
    ViolationType.WEEKLY_LOAD_EXCEEDS_CAPACITY: (
        "The plan exceeded your weekly hours. Trimming scope."
    ),
    ViolationType.NO_ROOT_TASK: (
        "The plan has no starting task — every task depends on another. "
        "Restructuring so something can begin."
    ),
    ViolationType.COGNITIVE_LOAD_OUT_OF_RANGE: (
        "A task's difficulty rating was invalid. Recalibrating."
    ),
    ViolationType.CATEGORY_INVALID: (
        "A task type was unrecognized. Replacing with a valid type."
    ),
    ViolationType.FOCUS_LEVEL_INVALID: (
        "A task's focus level was unrecognized. Replacing with a valid level."
    ),
    ViolationType.LOW_PRIORITY_MODULE_OVERWEIGHTED: (
        "Lower-priority work was taking over the plan. Re-balancing."
    ),
    ViolationType.HIGH_LOAD_TASKS_NOT_DISTRIBUTED: (
        "Heavy tasks were stacked together. Spreading them out."
    ),
    ViolationType.FORBIDDEN_FIELD_PRESENT: (
        "An internal field was set by the planner that the system computes "
        "itself. Re-running with the proper computation."
    ),
    ViolationType.REQUIRED_FIELD_MISSING: (
        "A required field was missing. Re-generating."
    ),
    ViolationType.FIELD_TYPE_INVALID: (
        "A field had an unexpected type. Re-generating."
    ),
    ViolationType.ENUM_VALUE_INVALID: (
        "A field had an unrecognized value. Re-generating."
    ),
    ViolationType.NUMERIC_OUT_OF_RANGE: (
        "A number was outside the allowed range. Re-generating."
    ),
}


def user_facing(violation_type: ViolationType) -> str:
    """Return the deterministic user-facing string for a violation type.

    Falls back to a generic message rather than raising, because a missing
    translation is a documentation bug rather than a runtime fault. The
    completeness test in ``tests/validation/test_translations.py`` enforces
    that every violation type has an entry.
    """
    return USER_FACING.get(
        violation_type,
        f"A check failed ({violation_type.value}). Re-generating.",
    )
