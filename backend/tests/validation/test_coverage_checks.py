"""Tests for ``validation.coverage.check_coverage``."""

from __future__ import annotations

from agentic_calendar.contracts.syllabus_units import SyllabusUnits
from agentic_calendar.contracts.violation_types import ViolationType
from agentic_calendar.validation.coverage import check_coverage
from tests._fixture_loader import iter_valid
from tests.validation._helpers import load_syllabus, make_plan, make_task


def _syllabus_with_low_priority_api_module() -> SyllabusUnits:
    """Fixture syllabus with ``api_design`` demoted to low priority."""
    payload = next(iter_valid("syllabus_units")).payload
    modules = [dict(m) for m in payload["modules"]]
    for m in modules:
        if m["module_id"] == "api_design":
            m["priority"] = "low"
    return SyllabusUnits.model_validate({**payload, "modules": modules})


def test_full_coverage_no_violations() -> None:
    syllabus = load_syllabus()
    plan = make_plan(
        make_task(task_id="dp_001", module_id="dp"),
        make_task(task_id="api_001", module_id="api_design"),
    )
    assert check_coverage(plan, syllabus) == []


def test_high_priority_module_uncovered() -> None:
    syllabus = load_syllabus()
    plan = make_plan(make_task(task_id="api_001", module_id="api_design"))
    violations = check_coverage(plan, syllabus)
    coverage = [
        v for v in violations if v.type is ViolationType.MODULE_COVERAGE_MISSING
    ]
    assert len(coverage) == 1
    assert coverage[0].module_id == "dp"
    assert coverage[0].details["priority"] == "high"


def test_low_priority_module_overweighted_reported() -> None:
    syllabus = _syllabus_with_low_priority_api_module()
    # Low-priority api_design consumes 300 of 400 total minutes (75% > 50%).
    plan = make_plan(
        make_task(task_id="dp_001", module_id="dp", estimated_duration_min=100),
        make_task(
            task_id="api_001", module_id="api_design", estimated_duration_min=300
        ),
    )
    violations = check_coverage(plan, syllabus)
    overweight = [
        v
        for v in violations
        if v.type is ViolationType.LOW_PRIORITY_MODULE_OVERWEIGHTED
    ]
    assert len(overweight) == 1
    assert overweight[0].module_id == "api_design"
    assert overweight[0].details["module_minutes"] == 300
    assert overweight[0].details["total_minutes"] == 400
    assert overweight[0].details["ratio"] == 0.75


def test_low_priority_overweight_ratio_boundary_is_strict() -> None:
    syllabus = _syllabus_with_low_priority_api_module()
    # Exactly 50% does NOT fire (rule is strictly greater than the ratio).
    plan = make_plan(
        make_task(task_id="dp_001", module_id="dp", estimated_duration_min=300),
        make_task(
            task_id="api_001", module_id="api_design", estimated_duration_min=300
        ),
    )
    violations = check_coverage(plan, syllabus)
    assert [
        v
        for v in violations
        if v.type is ViolationType.LOW_PRIORITY_MODULE_OVERWEIGHTED
    ] == []


def test_unknown_module_id_reported() -> None:
    syllabus = load_syllabus()
    plan = make_plan(
        make_task(task_id="t1", module_id="dp"),
        make_task(task_id="t2", module_id="dp"),
        make_task(task_id="ghost", module_id="not_in_syllabus"),
    )
    violations = check_coverage(plan, syllabus)
    missing = [v for v in violations if v.type is ViolationType.MISSING_MODULE_ID]
    assert len(missing) == 1
    assert missing[0].task_id == "ghost"
    assert missing[0].module_id == "not_in_syllabus"
