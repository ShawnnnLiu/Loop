"""Tests for ``validation.coverage.check_coverage``."""

from __future__ import annotations

from agentic_calendar.contracts.violation_types import ViolationType
from agentic_calendar.validation.coverage import check_coverage
from tests.validation._helpers import load_syllabus, make_plan, make_task


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
