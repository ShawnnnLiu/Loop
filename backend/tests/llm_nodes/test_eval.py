"""Tests for the eval harness — deterministic rates over recorded outputs."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from agentic_calendar.llm_nodes.call_log import LlmCallLog
from agentic_calendar.llm_nodes.eval import (
    EvalCase,
    EvalError,
    EvalRecording,
    EvalSet,
    EvalThresholds,
    aggregate_calls,
    compare_reports,
    grade_recording,
    threshold_breaches,
)

BACKEND_ROOT = Path(__file__).resolve().parents[2]
EVALSETS = BACKEND_ROOT / "evalsets"


def _load(path: Path) -> dict[str, object]:
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    assert isinstance(data, dict)
    return data


@pytest.fixture(scope="module")
def eval_set() -> EvalSet:
    return EvalSet.model_validate(_load(EVALSETS / "eval_set_v1.json"))


@pytest.fixture(scope="module")
def baseline() -> EvalRecording:
    return EvalRecording.model_validate(_load(EVALSETS / "recordings" / "fixture_baseline.json"))


@pytest.fixture(scope="module")
def improved() -> EvalRecording:
    return EvalRecording.model_validate(_load(EVALSETS / "recordings" / "fixture_improved.json"))


def test_baseline_rates_exact(eval_set: EvalSet, baseline: EvalRecording) -> None:
    """The shipped baseline recording has known, hand-computable rates."""
    report = grade_recording(eval_set, baseline)
    assert report.overall.cases == 6
    assert report.overall.schema_valid_first_attempt == 4
    assert report.overall.recovered_by_repair == 1
    assert report.overall.invalid_after_repair == 1
    assert report.overall.schema_validity_rate == 4 / 6
    assert report.overall.repair_recovery_rate == 1 / 2
    assert report.overall.post_repair_invalid_rate == 1 / 6

    planner = report.per_node["planner"]
    assert planner.schema_validity_rate == 1 / 2
    assert planner.repair_recovery_rate == 1.0
    assert planner.post_repair_invalid_rate == 0.0

    strategist = report.per_node["strategist"]
    assert strategist.schema_validity_rate == 1 / 2
    assert strategist.repair_recovery_rate == 0.0
    assert strategist.post_repair_invalid_rate == 1 / 2

    # Rubric applies to the two substring cases plus the two prose nodes,
    # and all four valid outputs satisfy it.
    assert report.overall.rubric_graded == 4
    assert report.overall.rubric_passed == 4
    assert report.overall.rubric_pass_rate == 1.0


def test_improved_rates_exact(eval_set: EvalSet, improved: EvalRecording) -> None:
    report = grade_recording(eval_set, improved)
    assert report.overall.schema_validity_rate == 1.0
    assert report.overall.repair_recovery_rate is None  # nothing to recover
    assert report.overall.post_repair_invalid_rate == 0.0


def test_threshold_breach_on_baseline(eval_set: EvalSet, baseline: EvalRecording) -> None:
    report = grade_recording(eval_set, baseline)
    breaches = threshold_breaches(report, EvalThresholds())
    assert len(breaches) == 1
    assert "post_repair_invalid_rate" in breaches[0]
    assert "axiom 09" in breaches[0]


def test_no_breach_on_improved(eval_set: EvalSet, improved: EvalRecording) -> None:
    report = grade_recording(eval_set, improved)
    assert threshold_breaches(report, EvalThresholds()) == []


def test_compare_reports_deltas(
    eval_set: EvalSet, baseline: EvalRecording, improved: EvalRecording
) -> None:
    before = grade_recording(eval_set, baseline)
    after = grade_recording(eval_set, improved)
    comparison = compare_reports(before, after)
    by_metric = {rc.metric: rc for rc in comparison.overall}
    validity = by_metric["schema_validity_rate"]
    assert validity.before == 4 / 6
    assert validity.after == 1.0
    assert validity.delta == 1.0 - 4 / 6
    # recovery is None after (denominator empty) -> delta undefined, not zero.
    recovery = by_metric["repair_recovery_rate"]
    assert recovery.after is None
    assert recovery.delta is None


def test_compare_rejects_mismatched_eval_sets(
    eval_set: EvalSet, baseline: EvalRecording
) -> None:
    report = grade_recording(eval_set, baseline)
    payload = report.model_dump(mode="json")
    payload["eval_set_version"] = "v2"
    other = type(report).model_validate(payload)
    with pytest.raises(EvalError, match="cannot compare across eval sets"):
        compare_reports(report, other)


# --- strictness: no silent skips, bounded attempts ---


def _single_case_set(node: str = "reflection_summary", **case_kwargs: object) -> EvalSet:
    return EvalSet.model_validate(
        {
            "eval_set_version": "vt",
            "cases": [{"case_id": "c1", "node": node, **case_kwargs}],
        }
    )


def test_missing_case_output_is_error() -> None:
    eval_set = _single_case_set()
    recording = EvalRecording(prompt_version="p", model_name="m", outputs={})
    with pytest.raises(EvalError, match="no outputs for cases"):
        grade_recording(eval_set, recording)


def test_unknown_case_output_is_error() -> None:
    eval_set = _single_case_set()
    recording = EvalRecording(
        prompt_version="p",
        model_name="m",
        outputs={"c1": [{"summary": "ok", "detail": []}], "ghost": []},
    )
    with pytest.raises(EvalError, match="unknown cases"):
        grade_recording(eval_set, recording)


def test_empty_attempt_list_is_error() -> None:
    eval_set = _single_case_set()
    recording = EvalRecording(prompt_version="p", model_name="m", outputs={"c1": []})
    with pytest.raises(EvalError, match="empty attempt list"):
        grade_recording(eval_set, recording)


def test_attempts_beyond_repair_cap_rejected() -> None:
    """Four attempts would mean a third repair — the axiom 04 cap forbids it."""
    eval_set = _single_case_set()
    attempt = {"summary": "ok", "detail": []}
    recording = EvalRecording(
        prompt_version="p", model_name="m", outputs={"c1": [attempt] * 4}
    )
    with pytest.raises(EvalError, match="at most 3"):
        grade_recording(eval_set, recording)


def test_duplicate_case_ids_rejected() -> None:
    with pytest.raises(ValidationError, match="duplicate case_id"):
        EvalSet.model_validate(
            {
                "eval_set_version": "vt",
                "cases": [
                    {"case_id": "c1", "node": "planner"},
                    {"case_id": "c1", "node": "strategist"},
                ],
            }
        )


# --- rubric ---


def test_rubric_fails_on_psychological_label() -> None:
    """A schema-valid reflection that labels identity fails the rubric (axiom 07)."""
    eval_set = _single_case_set()
    recording = EvalRecording(
        prompt_version="p",
        model_name="m",
        outputs={"c1": [{"summary": "You have been lazy this week.", "detail": []}]},
    )
    report = grade_recording(eval_set, recording)
    assert report.overall.schema_validity_rate == 1.0  # contract-valid...
    assert report.overall.rubric_pass_rate == 0.0  # ...but rubric-failing


def test_rubric_fails_on_missing_required_substring() -> None:
    eval_set = _single_case_set(required_substrings=["estimates"])
    recording = EvalRecording(
        prompt_version="p",
        model_name="m",
        outputs={"c1": [{"summary": "Plan adjusted.", "detail": []}]},
    )
    report = grade_recording(eval_set, recording)
    assert report.overall.rubric_pass_rate == 0.0


def test_rubric_not_graded_without_valid_output() -> None:
    eval_set = _single_case_set(required_substrings=["estimates"])
    recording = EvalRecording(
        prompt_version="p", model_name="m", outputs={"c1": [{"not_the_contract": True}]}
    )
    report = grade_recording(eval_set, recording)
    assert report.overall.rubric_graded == 0
    assert report.overall.rubric_pass_rate is None


# --- call aggregates ---


def _call(log_id: str, node: str, in_tok: int, out_tok: int, cost: float, ms: int) -> LlmCallLog:
    return LlmCallLog.model_validate(
        {
            "llm_call_log_id": log_id,
            "run_id": "run_agg",
            "node": node,
            "prompt_version": "p",
            "model_name": "m",
            "attempt": 0,
            "input_tokens": in_tok,
            "output_tokens": out_tok,
            "cost_estimate_usd": cost,
            "latency_ms": ms,
            "validation_outcome": "pass",
            "created_at": "2026-06-10T14:05:00-07:00",
        }
    )


def test_aggregate_calls_exact() -> None:
    calls = [
        _call("l1", "planner", 6000, 7000, 0.005, 9000),
        _call("l2", "planner", 6500, 6000, 0.004, 7000),
        _call("l3", "strategist", 8000, 4000, 0.084, 12000),
    ]
    aggregates = aggregate_calls(calls)
    planner = aggregates["planner"]
    assert planner.calls == 2
    assert planner.total_input_tokens == 12500
    assert planner.total_output_tokens == 13000
    assert planner.total_cost_estimate_usd == 0.005 + 0.004
    assert planner.mean_latency_ms == 8000.0
    assert aggregates["strategist"].calls == 1


def test_eval_case_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        EvalCase.model_validate(
            {"case_id": "c1", "node": "planner", "expected_prose": "exact words"}
        )


# --------------------------------------------------------------------------- #
# Tier-1 plan quality + Tier-2 judge plumbing (UX pass C2)
# --------------------------------------------------------------------------- #


def test_plan_quality_metrics_measure_depth_titles_and_granularity() -> None:
    from agentic_calendar.contracts.task_plan import TaskPlan
    from agentic_calendar.llm_nodes.eval import plan_quality_metrics

    def task(task_id: str, deps: list[str], title: str) -> dict[str, object]:
        return {
            "task_id": task_id,
            "module_id": "dp",
            "title": title,
            "dependencies": deps,
            "estimated_duration_min": 60,
            "cognitive_load": 3,
            "category": "practice",
            "required_focus_level": "medium",
            "splittable": False,
        }

    plan = TaskPlan.model_validate(
        {
            "plan_version": "p1",
            "tasks": [
                task("a", [], "Review the basics"),
                task("b", ["a"], "Solve two problems"),
                task("c", ["b"], "Solve two problems"),  # duplicate title
            ],
        }
    )
    metrics = plan_quality_metrics([plan])
    assert metrics is not None
    assert metrics.plans_graded == 1
    assert metrics.mean_max_dependency_depth == 3.0  # a -> b -> c
    assert metrics.mean_distinct_title_ratio == round(2 / 3, 4)
    assert metrics.mean_tasks_per_module == 3.0
    assert plan_quality_metrics([]) is None


def test_grade_recording_rejects_judge_scores_for_unknown_cases() -> None:
    from agentic_calendar.llm_nodes.call_log import LlmNodeName
    from agentic_calendar.llm_nodes.eval import (
        EvalCase,
        EvalError,
        EvalRecording,
        EvalSet,
        grade_recording,
    )

    eval_set = EvalSet(
        eval_set_version="vt",
        cases=[
            EvalCase(
                case_id="reflection_case",
                node=LlmNodeName.REFLECTION_SUMMARY,
            )
        ],
    )
    recording = EvalRecording(
        prompt_version="t",
        model_name="m",
        outputs={"reflection_case": [{"summary": "Steady progress.", "detail": []}]},
        judge_scores={"ghost_case": {"tone": 5, "specificity": 5, "actionability": 5}},
    )
    with pytest.raises(EvalError, match="unknown cases"):
        grade_recording(eval_set, recording)
