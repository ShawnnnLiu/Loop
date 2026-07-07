"""Tier-1 grounding metrics + Tier-2 groundedness judge (grounding-RAG G-H).

Hand-computed fixtures throughout: a grounded strategist case (two claims,
one medium / one low bucket) and its ungrounded twin, graded against known
outputs so every rate is checkable by eye. No network — the judge runs over
a canned transport.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel

from agentic_calendar.contracts.source_claim import SourceClaim
from agentic_calendar.llm_nodes.anthropic_adapter import TransportResult
from agentic_calendar.llm_nodes.eval import (
    EvalError,
    EvalRecording,
    EvalSet,
    EvalThresholds,
    compare_reports,
    grade_recording,
    threshold_breaches,
)
from agentic_calendar.llm_nodes.eval_judge import judge_groundedness
from tests._fixture_loader import iter_valid

_EVAL_SET_V3 = Path(__file__).parents[2] / "evalsets" / "eval_set_v3.json"


def _module(module_id: str, cited: list[str]) -> dict[str, Any]:
    return {
        "module_id": module_id,
        "title": f"Module {module_id}",
        "priority": "high",
        "reason": "Listed weakness.",
        "target_outcomes": ["Outcome"],
        "estimated_total_min": 300,
        "difficulty": 3,
        "source_claim_ids": cited,
    }


def _syllabus(modules: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "syllabus_version": "syl_grounding_test",
        "goal_summary": "Prepare for interviews with cited evidence.",
        "modules": modules,
    }


_EVAL_SET = EvalSet.model_validate(
    {
        "eval_set_version": "vtest",
        "cases": [
            {
                "case_id": "grounded",
                "node": "strategist",
                "inputs": {
                    "source_claims": [
                        {"claim_id": "claim_med", "confidence_bucket": "medium"},
                        {"claim_id": "claim_low", "confidence_bucket": "low"},
                    ]
                },
            },
            {
                "case_id": "ungrounded",
                "node": "strategist",
                "inputs": {"source_claims": []},
            },
        ],
    }
)

#: grounded: module m1 cites both supplied claims, m2 cites a fabricated id
#: → coverage 1/2, utilization 2/2, share 1/2 (one medium of two valid
#: citations), unknown 1. ungrounded twin cites claim_med against an empty
#: claim set → one more unknown citation, coverage/utilization untouched.
_RECORDING = EvalRecording.model_validate(
    {
        "prompt_version": "grounding-test",
        "model_name": "fixture",
        "outputs": {
            "grounded": [
                _syllabus(
                    [
                        _module("m1", ["claim_med", "claim_low"]),
                        _module("m2", ["claim_ghost"]),
                    ]
                )
            ],
            "ungrounded": [_syllabus([_module("m1", ["claim_med"])])],
        },
    }
)


def test_grounding_metrics_hand_computed() -> None:
    report = grade_recording(_EVAL_SET, _RECORDING)
    grounding = report.grounding
    assert grounding is not None
    assert grounding.cases_with_claims == 1
    assert grounding.cases_without_claims == 1
    assert grounding.citation_coverage == 0.5
    assert grounding.claim_utilization == 1.0
    assert grounding.high_confidence_share == 0.5
    assert grounding.unknown_citation_count == 2


def test_grounding_is_none_without_a_valid_strategist_output() -> None:
    recording = EvalRecording.model_validate(
        {
            "prompt_version": "grounding-test",
            "model_name": "fixture",
            "outputs": {"grounded": [{}], "ungrounded": [{}]},
        }
    )
    report = grade_recording(_EVAL_SET, recording)
    assert report.grounding is None


def test_citation_coverage_floor_is_gateable_and_vacuous_without_grounding() -> None:
    report = grade_recording(_EVAL_SET, _RECORDING)
    breached = threshold_breaches(report, EvalThresholds(min_citation_coverage=0.9))
    assert any("citation_coverage" in b for b in breached)
    assert not threshold_breaches(report, EvalThresholds(min_citation_coverage=0.4))

    # No grounding computed → the floor is vacuously satisfied, like the
    # repair-recovery floor on recordings where nothing needed repair.
    empty = grade_recording(
        _EVAL_SET,
        EvalRecording.model_validate(
            {
                "prompt_version": "grounding-test",
                "model_name": "fixture",
                "outputs": {"grounded": [{}], "ungrounded": [{}]},
            }
        ),
    )
    vacuous = threshold_breaches(empty, EvalThresholds(min_citation_coverage=0.9))
    assert not any("citation_coverage" in b for b in vacuous)


def test_groundedness_scores_copied_through_and_unknown_ids_error() -> None:
    scored = EvalRecording.model_validate(
        {
            **_RECORDING.model_dump(),
            "groundedness_scores": {"grounded": {"groundedness": 4}},
        }
    )
    report = grade_recording(_EVAL_SET, scored)
    assert report.groundedness_scores["grounded"].groundedness == 4

    unknown = EvalRecording.model_validate(
        {
            **_RECORDING.model_dump(),
            "groundedness_scores": {"nope": {"groundedness": 4}},
        }
    )
    with pytest.raises(EvalError):
        grade_recording(_EVAL_SET, unknown)


def test_compare_reports_carries_grounding_deltas() -> None:
    report = grade_recording(_EVAL_SET, _RECORDING)
    comparison = compare_reports(report, report)
    by_metric = {rc.metric: rc for rc in comparison.overall}
    assert by_metric["citation_coverage"].delta == 0.0
    assert by_metric["claim_utilization"].before == 1.0
    assert by_metric["high_confidence_share"].after == 0.5


class _CannedJudgeTransport:
    """Returns a canned groundedness score; records the prompts it saw."""

    def __init__(self) -> None:
        self.user_prompts: list[str] = []

    def complete(
        self, *, output_contract: type[BaseModel], user_prompt: str, **_: Any
    ) -> TransportResult:
        assert output_contract.__name__ == "GroundednessScore"
        self.user_prompts.append(user_prompt)
        payload = {"groundedness": 4}
        return TransportResult(
            payload=payload,
            raw_text=json.dumps(payload),
            stop_reason="end_turn",
            input_tokens=50,
            output_tokens=10,
        )


def test_judge_groundedness_scores_every_valid_strategist_case() -> None:
    transport = _CannedJudgeTransport()
    scores, unjudged = judge_groundedness(
        _EVAL_SET,
        _RECORDING,
        transport=transport,  # type: ignore[arg-type]
    )
    assert scores == {
        "grounded": {"groundedness": 4},
        "ungrounded": {"groundedness": 4},
    }
    assert unjudged == []
    # The judge sees the case's claims (empty for the twin) and the syllabus.
    assert "claim_med" in transport.user_prompts[0]
    assert "Supplied evidence claims" in transport.user_prompts[1]


def test_judge_groundedness_skips_cases_without_valid_output() -> None:
    transport = _CannedJudgeTransport()
    invalid = EvalRecording.model_validate(
        {
            "prompt_version": "grounding-test",
            "model_name": "fixture",
            "outputs": {
                "grounded": [{}],
                "ungrounded": [_syllabus([_module("m1", [])])],
            },
        }
    )
    scores, unjudged = judge_groundedness(
        _EVAL_SET,
        invalid,
        transport=transport,  # type: ignore[arg-type]
    )
    assert set(scores) == {"ungrounded"}
    assert unjudged == []


# --------------------------------------------------------------------------- #
# the committed v3 eval set
# --------------------------------------------------------------------------- #


def test_eval_set_v3_twins_are_consistent() -> None:
    """Every grounded case pins full contract-valid claims from the real
    store; every ungrounded twin refs its grounded profile with an empty
    claim list — today's production, verbatim."""
    eval_set = EvalSet.model_validate(json.loads(_EVAL_SET_V3.read_text(encoding="utf-8")))
    assert eval_set.eval_set_version == "v3"
    by_id = {case.case_id: case for case in eval_set.cases}
    grounded = [c for c in eval_set.cases if c.case_id.endswith("_grounded")]
    ungrounded = [c for c in eval_set.cases if c.case_id.endswith("_ungrounded")]
    assert len(grounded) == 3 and len(ungrounded) == 3
    for case in grounded:
        claims = case.inputs["source_claims"]
        assert claims, f"{case.case_id} must carry a non-empty claim payload"
        for raw in claims:
            claim = SourceClaim.model_validate(raw)
            # Realistic payloads: only claims the D1 serving floor would keep.
            assert claim.confidence_score >= 0.30
    for case in ungrounded:
        assert case.inputs["source_claims"] == []
        ref = str(case.inputs["user_profile_ref"])
        assert ref in by_id and by_id[ref].inputs.get("user_profile")


def test_eval_set_v3_claims_do_not_overlap_fixture_claim_ids() -> None:
    """v3 claims are content-hash ids from the real corpus, disjoint from the
    hand-written fixture claim ids used by golden tests."""
    eval_set = EvalSet.model_validate(json.loads(_EVAL_SET_V3.read_text(encoding="utf-8")))
    fixture_ids = {str(fixture.payload["claim_id"]) for fixture in iter_valid("source_claim")}
    v3_ids = {
        str(raw["claim_id"])
        for case in eval_set.cases
        for raw in case.inputs.get("source_claims", [])
    }
    assert v3_ids and not v3_ids & fixture_ids
