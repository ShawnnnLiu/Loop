"""Capture tool + Tier-2 judge over fake transports (UX pass C2). No network."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from agentic_calendar.llm_nodes import InMemoryLlmCallLogStore
from agentic_calendar.llm_nodes.anthropic_adapter import TransportResult
from agentic_calendar.llm_nodes.call_log import LlmNodeName
from agentic_calendar.llm_nodes.eval import EvalSet, grade_recording
from agentic_calendar.llm_nodes.eval_judge import judge_recording
from agentic_calendar.tools.capture_eval_recordings import (
    capture,
    main,
    parse_case_inputs,
)

_EVAL_SET_PATH = Path(__file__).parents[2] / "evalsets" / "eval_set_v2.json"


def _load_set() -> EvalSet:
    return EvalSet.model_validate(json.loads(_EVAL_SET_PATH.read_text()))


_CANNED_SYLLABUS: dict[str, Any] = {
    "syllabus_version": "syl_canned",
    "goal_summary": "Prepare for backend interviews.",
    "modules": [
        {
            "module_id": "dp",
            "title": "Dynamic Programming",
            "priority": "high",
            "reason": "Listed weakness.",
            "target_outcomes": ["Recognize DP state definitions"],
            "estimated_total_min": 600,
            "difficulty": 5,
            "source_claim_ids": [],
        }
    ],
}

_CANNED_PLAN: dict[str, Any] = {
    "plan_version": "plan_canned",
    "tasks": [
        {
            "task_id": "dp_001",
            "module_id": "dp",
            "title": "Review DP state definitions",
            "dependencies": [],
            "estimated_duration_min": 60,
            "cognitive_load": 4,
            "category": "concept_review",
            "required_focus_level": "deep",
            "splittable": False,
        },
        {
            "task_id": "dp_002",
            "module_id": "dp",
            "title": "Solve two 1-D DP problems",
            "dependencies": ["dp_001"],
            "estimated_duration_min": 60,
            "cognitive_load": 4,
            "category": "practice",
            "required_focus_level": "deep",
            "splittable": False,
        },
    ],
}

_CANNED_PROSE: dict[str, Any] = {
    "summary": "Practice tasks are taking longer than planned.",
    "detail": ["Try shortening the next dynamic programming session."],
}


class _CannedTransport:
    """Returns a contract-appropriate canned payload for every call."""

    def __init__(self) -> None:
        self.calls = 0

    def complete(self, *, output_contract: type[BaseModel], **_: Any) -> TransportResult:
        self.calls += 1
        by_contract = {
            "SyllabusUnits": _CANNED_SYLLABUS,
            "TaskPlan": _CANNED_PLAN,
            "ReflectionSummary": _CANNED_PROSE,
            "UserExplanation": _CANNED_PROSE,
            "JudgeScore": {"tone": 4, "specificity": 3, "actionability": 5},
        }
        payload = by_contract[output_contract.__name__]
        return TransportResult(
            payload=payload,
            raw_text=json.dumps(payload),
            stop_reason="end_turn",
            input_tokens=100,
            output_tokens=50,
        )


def test_every_v2_case_parses_into_typed_node_inputs() -> None:
    eval_set = _load_set()
    by_id = {case.case_id: case for case in eval_set.cases}
    for case in eval_set.cases:
        kwargs = parse_case_inputs(case, by_id)
        assert kwargs  # every case produces real, contract-validated inputs


def test_capture_records_every_case_and_grades_cleanly() -> None:
    eval_set = _load_set()
    transport = _CannedTransport()
    recording = capture(
        eval_set,
        transport=transport,  # type: ignore[arg-type]
        store=InMemoryLlmCallLogStore(),
        label="canned-test",
    )

    assert set(recording.outputs) == {case.case_id for case in eval_set.cases}
    assert all(len(attempts) >= 1 for attempts in recording.outputs.values())

    report = grade_recording(eval_set, recording)
    assert report.prompt_version == "canned-test"
    # Canned outputs are contract-valid on the first attempt everywhere.
    assert report.overall.schema_validity_rate == 1.0
    # Tier-1 plan quality is computed from the recorded plans.
    assert report.plan_quality is not None
    assert report.plan_quality.plans_graded == 3
    assert report.plan_quality.mean_max_dependency_depth == 2.0
    assert report.plan_quality.mean_distinct_title_ratio == 1.0


def test_judge_scores_prose_cases_only_and_flows_into_the_report() -> None:
    eval_set = _load_set()
    transport = _CannedTransport()
    recording = capture(
        eval_set,
        transport=transport,  # type: ignore[arg-type]
        store=InMemoryLlmCallLogStore(),
        label="canned-test",
    )
    scores, unjudged = judge_recording(
        eval_set, recording, transport=transport  # type: ignore[arg-type]
    )

    prose_ids = {
        case.case_id
        for case in eval_set.cases
        if case.node
        in (LlmNodeName.REFLECTION_SUMMARY, LlmNodeName.USER_FACING_EXPLANATION)
    }
    assert set(scores) == prose_ids
    assert unjudged == []
    assert all(set(s) == {"tone", "specificity", "actionability"} for s in scores.values())

    judged = recording.model_validate(
        {**recording.model_dump(), "judge_scores": scores}
    )
    report = grade_recording(eval_set, judged)
    assert set(report.judge_scores) == prose_ids
    assert report.judge_scores[next(iter(prose_ids))].tone == 4


def test_cli_validate_only_is_offline_and_green() -> None:
    assert main(["--eval-set", str(_EVAL_SET_PATH), "--validate-only"]) == 0


def test_cli_refuses_live_without_flag_and_key(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert main(["--eval-set", str(_EVAL_SET_PATH)]) == 1
