"""Golden scenarios that exercise the Validation layer end-to-end.

Covers ``docs/golden-test-cases.md``:

* Scenario 3:  Cycle in task graph
* Scenario 4:  Orphan dependency
* Scenario 10: Malformed Planner JSON
* Scenario 11: Dropped high-priority module

Every scenario asserts:

* the typed ``ReasonCode``,
* the structured violations / repair payload,
* the Supervisor's next state from the deterministic transition table,
* validation does not mutate the artifact under test.
"""

from __future__ import annotations

from agentic_calendar.contracts.reason_codes import ReasonCode
from agentic_calendar.contracts.task_plan import TaskPlan
from agentic_calendar.contracts.validation_result import (
    MAX_REPAIR_ATTEMPTS_LLM,
    NextAction,
)
from agentic_calendar.contracts.violation_types import ViolationType
from agentic_calendar.supervisor import (
    SupervisorSignal,
    SupervisorState,
    route,
)
from agentic_calendar.validation import (
    RepairPayload,
    next_action_for,
    validate_task_plan,
)
from tests.golden.conftest import deep_copy_plan, make_task


def _signal_for(result_next_action: NextAction) -> SupervisorSignal:
    """Translate a ``NextAction`` into the Supervisor signal it implies."""
    if result_next_action is NextAction.SCHEDULER:
        return SupervisorSignal.VALIDATION_PASSED
    if result_next_action is NextAction.PLANNER_REPAIR_RETRY:
        return SupervisorSignal.VALIDATION_FAILED_REPAIRABLE
    if result_next_action is NextAction.ERROR_REQUIRES_USER:
        return SupervisorSignal.REPAIR_LIMIT_EXCEEDED
    raise AssertionError(f"unexpected next_action {result_next_action!r}")


# --------------------------------------------------------------------------- #
# Scenario 3 — Cycle in task graph
# --------------------------------------------------------------------------- #

def test_scenario_3_cycle_in_task_graph(syllabus, user_profile) -> None:  # type: ignore[no-untyped-def]
    plan = TaskPlan.model_validate({
        "plan_version": "p_cycle",
        "tasks": [
            make_task(task_id="a", dependencies=["b"]),
            make_task(task_id="b", dependencies=["a"]),
        ],
    })
    snapshot = deep_copy_plan(plan)

    result = validate_task_plan(
        plan, syllabus=syllabus, user_profile=user_profile, run_id="r3"
    )

    assert result.valid is False
    assert result.reason_code is ReasonCode.TASK_GRAPH_INVALID
    cycle_v = next(v for v in result.violations if v.type is ViolationType.CYCLE_DETECTED)
    # Contract: cycle_members is the canonical (smallest-rotated, no closing
    # repetition) list of unique cycle nodes. For ``a <-> b`` this is exactly
    # ``["a", "b"]``.
    assert cycle_v.details["cycle_members"] == ["a", "b"]
    assert "members" not in cycle_v.details

    assert result.next_action is NextAction.PLANNER_REPAIR_RETRY
    next_state = route(SupervisorState.PLANNER_VALIDATING, _signal_for(result.next_action))
    assert next_state is SupervisorState.PLANNER_RUNNING

    assert deep_copy_plan(plan) == snapshot


# --------------------------------------------------------------------------- #
# Scenario 4 — Orphan dependency
# --------------------------------------------------------------------------- #

def test_scenario_4_orphan_dependency(syllabus, user_profile) -> None:  # type: ignore[no-untyped-def]
    plan = TaskPlan.model_validate({
        "plan_version": "p_orphan",
        "tasks": [
            make_task(task_id="a", dependencies=["does_not_exist"]),
        ],
    })
    snapshot = deep_copy_plan(plan)

    result = validate_task_plan(
        plan, syllabus=syllabus, user_profile=user_profile, run_id="r4"
    )

    assert result.valid is False
    assert result.reason_code is ReasonCode.TASK_GRAPH_INVALID
    orphan_v = next(
        v for v in result.violations if v.type is ViolationType.ORPHAN_DEPENDENCY
    )
    assert orphan_v.task_id == "a"
    assert orphan_v.details["invalid_dependency"] == "does_not_exist"

    assert result.next_action is NextAction.PLANNER_REPAIR_RETRY
    next_state = route(SupervisorState.PLANNER_VALIDATING, _signal_for(result.next_action))
    assert next_state is SupervisorState.PLANNER_RUNNING

    assert deep_copy_plan(plan) == snapshot


# --------------------------------------------------------------------------- #
# Scenario 10 — Malformed Planner JSON, then repair-limit exhaustion
# --------------------------------------------------------------------------- #

def test_scenario_10_malformed_planner_json_routes_through_repair(
    syllabus, user_profile,  # type: ignore[no-untyped-def]
) -> None:
    bad_payload = {
        "plan_version": "p_bad",
        "tasks": [{"task_id": "a"}],
    }

    first = validate_task_plan(
        bad_payload, syllabus=syllabus, user_profile=user_profile,
        run_id="r10", repair_attempt=0,
    )
    assert first.valid is False
    assert first.reason_code is ReasonCode.SCHEMA_INVALID
    assert first.next_action is NextAction.PLANNER_REPAIR_RETRY
    assert (
        route(SupervisorState.PLANNER_VALIDATING, _signal_for(first.next_action))
        is SupervisorState.PLANNER_RUNNING
    )

    second = validate_task_plan(
        bad_payload, syllabus=syllabus, user_profile=user_profile,
        run_id="r10", repair_attempt=MAX_REPAIR_ATTEMPTS_LLM,
    )
    assert second.valid is False
    assert second.next_action is NextAction.ERROR_REQUIRES_USER
    assert (
        route(SupervisorState.PLANNER_VALIDATING, _signal_for(second.next_action))
        is SupervisorState.ERROR_REQUIRES_USER
    )


def test_scenario_10_repair_payload_typed_for_planner(
    syllabus, user_profile,  # type: ignore[no-untyped-def]
) -> None:
    bad_payload = {"plan_version": "p_bad", "tasks": [{"task_id": "a"}]}
    result = validate_task_plan(
        bad_payload, syllabus=syllabus, user_profile=user_profile, run_id="r10b"
    )
    assert result.valid is False
    payload = RepairPayload(
        artifact_type=result.artifact_type,
        attempt=1,
        violations=list(result.violations),
    )
    assert payload.attempt == 1
    assert payload.violations  # at least one violation
    assert all(v.type is ViolationType.REQUIRED_FIELD_MISSING for v in payload.violations)


# --------------------------------------------------------------------------- #
# Scenario 11 — Dropped high-priority module
# --------------------------------------------------------------------------- #

def test_scenario_11_dropped_high_priority_module_forces_repair(
    syllabus, user_profile,  # type: ignore[no-untyped-def]
) -> None:
    """Plan only covers ``api_design`` (medium); the ``dp`` (high) module is dropped."""
    plan = TaskPlan.model_validate({
        "plan_version": "p_low_only",
        "tasks": [
            make_task(task_id="a", module_id="api_design"),
        ],
    })
    snapshot = deep_copy_plan(plan)

    result = validate_task_plan(
        plan, syllabus=syllabus, user_profile=user_profile, run_id="r11"
    )

    assert result.valid is False
    assert result.reason_code is ReasonCode.MODULE_COVERAGE_INSUFFICIENT
    coverage_v = next(
        v for v in result.violations if v.type is ViolationType.MODULE_COVERAGE_MISSING
    )
    assert coverage_v.module_id == "dp"

    assert result.next_action is NextAction.PLANNER_REPAIR_RETRY
    next_state = route(SupervisorState.PLANNER_VALIDATING, _signal_for(result.next_action))
    assert next_state is SupervisorState.PLANNER_RUNNING

    assert deep_copy_plan(plan) == snapshot


# --------------------------------------------------------------------------- #
# Cross-cutting: typed reason_code is preserved end-to-end via next_action_for
# --------------------------------------------------------------------------- #

def test_next_action_helper_matches_repair_cap() -> None:
    """``next_action_for`` is the only place the supervisor learns about repair limits."""
    assert (
        next_action_for(valid=False, repair_attempt=0, repairable=True)
        is NextAction.PLANNER_REPAIR_RETRY
    )
    assert (
        next_action_for(
            valid=False, repair_attempt=MAX_REPAIR_ATTEMPTS_LLM, repairable=True
        )
        is NextAction.ERROR_REQUIRES_USER
    )
    assert (
        next_action_for(valid=True, repair_attempt=0, repairable=False)
        is NextAction.SCHEDULER
    )
