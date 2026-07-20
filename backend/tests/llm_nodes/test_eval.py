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


# --------------------------------------------------------------------------- #
# ResumeIntake grading (résumé intake RI-E)
# --------------------------------------------------------------------------- #

_INTAKE_INPUTS: dict[str, object] = {
    "intake": {
        "user_id": "user_eval",
        "resume_text": (
            "Senior Backend Engineer at Acme Corp\n"
            "Python and Go services on Kubernetes for the billing platform."
        ),
        "draft_context": {"target_role": "Backend SWE"},
        "allowed_weak_spots": ["System design", "Dynamic programming"],
    }
}

_GROUNDED_EXTRACTION: dict[str, object] = {
    "experience": [
        {
            "title": "Senior Backend Engineer",
            "organization": "Acme Corp",
            "summary": None,
        }
    ],
    "skills": ["Python", "Go"],
    "known_strengths": ["backend services"],
    "inferred_weak_spots": ["System design"],
    "target_company_categories": ["infra startups"],
}


def _resume_case_set(**case_kwargs: object) -> EvalSet:
    return EvalSet.model_validate(
        {
            "eval_set_version": "vt",
            "cases": [
                {
                    "case_id": "r1",
                    "node": "resume_intake",
                    "inputs": _INTAKE_INPUTS,
                    **case_kwargs,
                }
            ],
        }
    )


def test_resume_intake_validity_mirrors_the_live_repair_loop() -> None:
    """An attempt that is contract-valid but ungrounded was REPAIRED live
    (the post-validator runs inside the bounded loop), so grading must count
    it invalid — first-attempt validity may not overreport."""
    ungrounded = {**_GROUNDED_EXTRACTION, "skills": ["Python", "Flurbo.js"]}
    recording = EvalRecording(
        prompt_version="p",
        model_name="m",
        outputs={"r1": [ungrounded, _GROUNDED_EXTRACTION]},
    )
    report = grade_recording(_resume_case_set(), recording)
    assert report.overall.schema_valid_first_attempt == 0
    assert report.overall.recovered_by_repair == 1
    assert report.overall.post_repair_invalid_rate == 0.0


def test_resume_intake_out_of_vocabulary_weak_spot_never_grades_valid() -> None:
    out_of_vocab = {**_GROUNDED_EXTRACTION, "inferred_weak_spots": ["Excel"]}
    recording = EvalRecording(
        prompt_version="p", model_name="m", outputs={"r1": [out_of_vocab]}
    )
    report = grade_recording(_resume_case_set(), recording)
    assert report.overall.schema_validity_rate == 0.0
    assert report.overall.post_repair_invalid_rate == 1.0


def test_resume_intake_case_without_intake_inputs_refuses_to_grade() -> None:
    eval_set = _resume_case_set(inputs={})
    recording = EvalRecording(
        prompt_version="p", model_name="m", outputs={"r1": [_GROUNDED_EXTRACTION]}
    )
    with pytest.raises(EvalError, match=r"needs inputs\.intake"):
        grade_recording(eval_set, recording)


def test_taxonomy_version_pinning_rejects_mismatched_recording() -> None:
    eval_set = _resume_case_set(taxonomy_version="skill-taxonomy-v1")
    for recorded_version in ("skill-taxonomy-v2", None):
        recording = EvalRecording(
            prompt_version="p",
            model_name="m",
            outputs={"r1": [_GROUNDED_EXTRACTION]},
            taxonomy_version=recorded_version,
        )
        with pytest.raises(EvalError, match="taxonomy_version"):
            grade_recording(eval_set, recording)


def test_v3_fixture_recording_rates_exact() -> None:
    """The shipped resume_intake recording grades clean: contract-valid AND
    invariant-clean (groundedness, category hygiene, vocabulary membership)
    on the first attempt for all seven cases."""
    eval_set = EvalSet.model_validate(_load(EVALSETS / "eval_set_v3.json"))
    recording = EvalRecording.model_validate(
        _load(EVALSETS / "recordings" / "fixture_resume_intake.json")
    )
    assert recording.taxonomy_version == "skill-taxonomy-v1"
    report = grade_recording(eval_set, recording)
    assert report.overall.cases == 7
    assert report.overall.schema_validity_rate == 1.0
    assert report.overall.post_repair_invalid_rate == 0.0
    # Only the dense case pins a required substring; it passes.
    assert report.overall.rubric_graded == 1
    assert report.overall.rubric_pass_rate == 1.0


def test_v5_fixture_recording_rates_exact() -> None:
    """The v5 set re-pins the seven v3 cases to skill-taxonomy-v2 and adds
    the two data_analyst cases (track resolution + the GlimmerBI
    out-of-vocabulary trap); the fixture twin grades clean on all nine."""
    eval_set = EvalSet.model_validate(_load(EVALSETS / "eval_set_v5.json"))
    recording = EvalRecording.model_validate(
        _load(EVALSETS / "recordings" / "fixture_resume_intake_v5.json")
    )
    assert recording.taxonomy_version == "skill-taxonomy-v2"
    report = grade_recording(eval_set, recording)
    assert report.overall.cases == 9
    assert report.overall.schema_validity_rate == 1.0
    assert report.overall.post_repair_invalid_rate == 0.0
    # The dense backend case pins "Python"; the data-analyst case pins "SQL".
    assert report.overall.rubric_graded == 2
    assert report.overall.rubric_pass_rate == 1.0


def test_v6_fixture_recording_rates_exact() -> None:
    """The v6 set re-pins the nine v5 cases to skill-taxonomy-v3 and adds
    the two data_scientist cases (track resolution + the QuantaViz
    out-of-vocabulary trap); the fixture twin grades clean on all eleven."""
    eval_set = EvalSet.model_validate(_load(EVALSETS / "eval_set_v6.json"))
    recording = EvalRecording.model_validate(
        _load(EVALSETS / "recordings" / "fixture_resume_intake_v6.json")
    )
    assert recording.taxonomy_version == "skill-taxonomy-v3"
    report = grade_recording(eval_set, recording)
    assert report.overall.cases == 11
    assert report.overall.schema_validity_rate == 1.0
    assert report.overall.post_repair_invalid_rate == 0.0
    # Pinned substrings: dense backend "Python", data-analyst "SQL",
    # data-scientist "Python".
    assert report.overall.rubric_graded == 3
    assert report.overall.rubric_pass_rate == 1.0


def test_v7_fixture_recording_rates_exact() -> None:
    """The v7 set re-pins the eleven v6 cases to skill-taxonomy-v4 and adds
    the two data_engineer cases (track resolution + the PipeForge
    out-of-vocabulary trap); the fixture twin grades clean on all thirteen."""
    eval_set = EvalSet.model_validate(_load(EVALSETS / "eval_set_v7.json"))
    recording = EvalRecording.model_validate(
        _load(EVALSETS / "recordings" / "fixture_resume_intake_v7.json")
    )
    assert recording.taxonomy_version == "skill-taxonomy-v4"
    report = grade_recording(eval_set, recording)
    assert report.overall.cases == 13
    assert report.overall.schema_validity_rate == 1.0
    assert report.overall.post_repair_invalid_rate == 0.0
    # Pinned substrings: dense backend "Python", data-analyst "SQL",
    # data-scientist "Python", data-engineer "SQL".
    assert report.overall.rubric_graded == 4
    assert report.overall.rubric_pass_rate == 1.0


def test_v8_fixture_recording_rates_exact() -> None:
    """The v8 set carries the thirteen v7 cases forward and adds three
    evidence-tagging cases (NP-C): a project/volunteering split, a sparse
    résumé whose tags stay empty, and an off-vocabulary theme attempt that the
    deterministic theme-membership check rejects on attempt 0 and the repair
    attempt fixes — the one recovered-by-repair case in the twin."""
    eval_set = EvalSet.model_validate(_load(EVALSETS / "eval_set_v8.json"))
    recording = EvalRecording.model_validate(
        _load(EVALSETS / "recordings" / "fixture_resume_intake_v8.json")
    )
    assert recording.taxonomy_version == "skill-taxonomy-v4"
    report = grade_recording(eval_set, recording)
    assert report.overall.cases == 16
    # Fifteen valid on the first attempt; the off-vocabulary-theme case needs
    # one repair, so validity is 15/16 and nothing stays invalid after repair.
    assert report.overall.schema_valid_first_attempt == 15
    assert report.overall.recovered_by_repair == 1
    assert report.overall.repair_recovery_rate == 1.0
    assert report.overall.post_repair_invalid_rate == 0.0
    assert report.overall.rubric_graded == 4
    assert report.overall.rubric_pass_rate == 1.0


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
