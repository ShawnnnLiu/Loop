"""Tests for ``contracts.violation_types.ViolationType``."""

from __future__ import annotations

from agentic_calendar.contracts.violation_types import ViolationType


def test_values_are_snake_case_strings() -> None:
    for v in ViolationType:
        assert isinstance(v.value, str)
        assert v.value == v.value.lower(), v
        assert " " not in v.value
        assert "-" not in v.value


def test_phase_1_violation_types_present() -> None:
    """All violation types referenced in axiom 04 must be defined."""
    required = {
        "orphan_dependency",
        "cycle_detected",
        "self_dependency",
        "duplicate_task_id",
        "missing_module_id",
        "module_coverage_missing",
        "duration_exceeds_user_max_session",
        "cognitive_load_out_of_range",
        "category_invalid",
        "focus_level_invalid",
        "weekly_load_exceeds_capacity",
        "forbidden_field_present",
    }
    present = {v.value for v in ViolationType}
    assert required.issubset(present)


def test_round_trip_from_string() -> None:
    v = ViolationType("orphan_dependency")
    assert v is ViolationType.ORPHAN_DEPENDENCY
