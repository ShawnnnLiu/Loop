"""Tests for ``contracts.reason_codes.ReasonCode``."""

from __future__ import annotations

from agentic_calendar.contracts.reason_codes import ReasonCode


def test_values_are_screaming_snake_case_strings() -> None:
    for code in ReasonCode:
        assert isinstance(code.value, str)
        assert code.value == code.value.upper(), code
        assert " " not in code.value
        assert "-" not in code.value


def test_value_equals_name() -> None:
    """Convention: enum name and string value must match exactly.

    This makes JSON serialization round-trip cleanly with no name/value drift.
    """
    for code in ReasonCode:
        assert code.name == code.value, code


def test_phase_1_validation_codes_present() -> None:
    required = {
        "VALIDATION_FAILED",
        "SCHEMA_INVALID",
        "TASK_GRAPH_INVALID",
        "MODULE_COVERAGE_INSUFFICIENT",
        "USER_FIT_VIOLATED",
        "SCHEDULING_PRECONDITION_FAILED",
        "REPAIR_LIMIT_EXCEEDED",
        "FORBIDDEN_FIELD_PRESENT",
    }
    present = {c.value for c in ReasonCode}
    assert required.issubset(present)


def test_phase_1_scheduler_codes_present() -> None:
    """Every scheduler reason code from axiom 05 must be defined."""
    required = {
        "NO_VALID_CONTIGUOUS_BLOCK",
        "INSUFFICIENT_WEEKLY_CAPACITY",
        "DEPENDENCY_BLOCKED",
        "OUTSIDE_ALLOWED_HOURS",
        "DAILY_LOAD_EXCEEDED",
        "DEEP_WORK_REQUIRED_UNAVAILABLE",
        "TASK_TOO_LONG_UNSPLITTABLE",
    }
    present = {c.value for c in ReasonCode}
    assert required.issubset(present)


def test_serializes_to_string() -> None:
    import json

    payload = json.dumps({"reason_code": ReasonCode.NO_VALID_CONTIGUOUS_BLOCK})
    assert "NO_VALID_CONTIGUOUS_BLOCK" in payload


def test_round_trip_from_string() -> None:
    code = ReasonCode("INSUFFICIENT_WEEKLY_CAPACITY")
    assert code is ReasonCode.INSUFFICIENT_WEEKLY_CAPACITY
