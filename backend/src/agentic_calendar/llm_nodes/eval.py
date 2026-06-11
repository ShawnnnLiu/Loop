"""LLM eval harness — pure metric computation over recorded outputs (Phase 8).

Axiom 22 separates two test surfaces: golden tests grade the *deterministic
system* (exact, per-commit), while this harness grades *model output quality*
as aggregate rates against thresholds. Everything here is a pure function over
recorded data: validating a recorded proposal against its target contract,
counting repair recoveries inside the bounded cap, applying deterministic
rubrics, and aggregating :class:`LlmCallLog` rows. Nothing here calls a model,
and nothing here may feed runtime routing — eval is offline by definition.

Honesty constraint (axiom 09 disclosure rules): rates computed over fixture
recordings prove the *harness*, not model quality. Real before/after numbers
require recordings captured from real adapters (Phase 8c+).
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from agentic_calendar.common.errors import AgenticCalendarError
from agentic_calendar.contracts.syllabus_units import SyllabusUnits
from agentic_calendar.contracts.task_plan import TaskPlan

from .call_log import LlmCallLog, LlmNodeName
from .reflection_summary import _PSYCH_DENYLIST, ReflectionSummary
from .user_facing_explanation import UserExplanation

#: Attempt 0 plus the bounded two repair re-prompts (axiom 04). A recording
#: with more attempts than this is itself a cap violation and is rejected.
MAX_RECORDED_ATTEMPTS = 3

#: The contract each node's recorded output must satisfy (axiom 22: the eval
#: set measures whether proposals satisfy the deterministic contracts).
TARGET_CONTRACTS: Mapping[LlmNodeName, type[BaseModel]] = {
    LlmNodeName.STRATEGIST: SyllabusUnits,
    LlmNodeName.PLANNER: TaskPlan,
    LlmNodeName.REFLECTION_SUMMARY: ReflectionSummary,
    LlmNodeName.USER_FACING_EXPLANATION: UserExplanation,
}

#: Nodes whose output is user-facing prose; graded against the axiom 07
#: behavior-not-identity rubric (the same denylist the live node enforces).
_PROSE_NODES: frozenset[LlmNodeName] = frozenset(
    {LlmNodeName.REFLECTION_SUMMARY, LlmNodeName.USER_FACING_EXPLANATION}
)


class EvalError(AgenticCalendarError):
    """A recording/eval-set mismatch the harness refuses to grade silently."""


class EvalCase(BaseModel):
    """One eval case: a node, an implied target contract, and its rubric."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str = Field(min_length=1)
    node: LlmNodeName
    description: str = ""
    required_substrings: list[str] = Field(default_factory=list)


class EvalSet(BaseModel):
    """Curated, versioned, append-only eval set (axiom 22 "Fixed Eval Set")."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    eval_set_version: str = Field(min_length=1)
    cases: list[EvalCase] = Field(min_length=1)

    @model_validator(mode="after")
    def _case_ids_unique(self) -> EvalSet:
        seen: set[str] = set()
        for case in self.cases:
            if case.case_id in seen:
                raise ValueError(f"duplicate case_id {case.case_id!r}")
            seen.add(case.case_id)
        return self


class EvalRecording(BaseModel):
    """Recorded raw outputs for one (prompt_version, model_name) run.

    ``outputs`` maps ``case_id`` to the attempt sequence: index 0 is the raw
    first proposal, indexes 1 and 2 the bounded repair re-prompts."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    prompt_version: str = Field(min_length=1)
    model_name: str = Field(min_length=1)
    outputs: dict[str, list[dict[str, Any]]]


class NodeMetrics(BaseModel):
    """Aggregate rates for one node (or overall). Counts kept for audit."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    cases: int
    schema_valid_first_attempt: int
    recovered_by_repair: int
    invalid_after_repair: int
    schema_validity_rate: float
    repair_recovery_rate: float | None
    post_repair_invalid_rate: float
    rubric_graded: int
    rubric_passed: int
    rubric_pass_rate: float | None


class CallAggregates(BaseModel):
    """Latency/token/cost aggregates read from observability records."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    calls: int
    total_input_tokens: int
    total_output_tokens: int
    total_cost_estimate_usd: float
    mean_latency_ms: float


class EvalReport(BaseModel):
    """One graded eval run, tagged for reproducible before/after comparison."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    eval_set_version: str
    prompt_version: str
    model_name: str
    per_node: dict[str, NodeMetrics]
    overall: NodeMetrics
    call_aggregates: dict[str, CallAggregates] = Field(default_factory=dict)


class EvalThresholds(BaseModel):
    """Alert thresholds. Eval runs report against these; they never gate CI."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    max_post_repair_invalid_rate: float = Field(default=0.05, ge=0, le=1)
    """Axiom 09 target: invalid Planner output rate <5% after repair."""


class RateComparison(BaseModel):
    """Before/after on one metric; ``delta`` is None when either side is."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    metric: str
    before: float | None
    after: float | None
    delta: float | None


class EvalComparison(BaseModel):
    """Before/after report across two graded runs of the same eval set."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    eval_set_version: str
    before_prompt_version: str
    after_prompt_version: str
    before_model_name: str
    after_model_name: str
    overall: list[RateComparison]
    per_node: dict[str, list[RateComparison]]


class _CaseGrade(BaseModel):
    """Internal per-case grading result."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    node: LlmNodeName
    valid_attempt: int | None
    rubric_applies: bool
    rubric_passed: bool


def _contains_psych_label(text: str) -> bool:
    lowered = text.lower()
    return any(re.search(rf"\b{re.escape(term)}\b", lowered) for term in _PSYCH_DENYLIST)


def _first_valid_attempt(
    case: EvalCase, attempts: Sequence[Mapping[str, Any]]
) -> tuple[int | None, BaseModel | None]:
    contract = TARGET_CONTRACTS[case.node]
    for index, payload in enumerate(attempts):
        try:
            return index, contract.model_validate(payload)
        except ValidationError:
            continue
    return None, None


def _grade_rubric(case: EvalCase, validated: BaseModel) -> bool:
    canonical = json.dumps(validated.model_dump(mode="json"), sort_keys=True)
    if any(substr not in canonical for substr in case.required_substrings):
        return False
    if case.node in _PROSE_NODES:
        # Both prose contracts share the summary/detail shape.
        summary: str = validated.summary  # type: ignore[attr-defined]
        detail: list[str] = validated.detail  # type: ignore[attr-defined]
        if _contains_psych_label(summary) or any(_contains_psych_label(d) for d in detail):
            return False
    return True


def _grade_case(case: EvalCase, attempts: Sequence[Mapping[str, Any]]) -> _CaseGrade:
    if not attempts:
        raise EvalError(f"case {case.case_id!r} has an empty attempt list")
    if len(attempts) > MAX_RECORDED_ATTEMPTS:
        raise EvalError(
            f"case {case.case_id!r} records {len(attempts)} attempts; the bounded "
            f"repair cap allows at most {MAX_RECORDED_ATTEMPTS} (axiom 04)"
        )
    valid_attempt, validated = _first_valid_attempt(case, attempts)
    rubric_applies = bool(case.required_substrings) or case.node in _PROSE_NODES
    rubric_passed = (
        rubric_applies and validated is not None and _grade_rubric(case, validated)
    )
    return _CaseGrade(
        node=case.node,
        valid_attempt=valid_attempt,
        rubric_applies=rubric_applies,
        rubric_passed=rubric_passed,
    )


def _metrics_from_grades(grades: Sequence[_CaseGrade]) -> NodeMetrics:
    cases = len(grades)
    valid_first = sum(1 for g in grades if g.valid_attempt == 0)
    initially_invalid = cases - valid_first
    recovered = sum(1 for g in grades if g.valid_attempt is not None and g.valid_attempt > 0)
    invalid_after = initially_invalid - recovered
    rubric_graded = sum(1 for g in grades if g.rubric_applies and g.valid_attempt is not None)
    rubric_passed = sum(1 for g in grades if g.rubric_passed)
    return NodeMetrics(
        cases=cases,
        schema_valid_first_attempt=valid_first,
        recovered_by_repair=recovered,
        invalid_after_repair=invalid_after,
        schema_validity_rate=valid_first / cases,
        repair_recovery_rate=(recovered / initially_invalid) if initially_invalid else None,
        post_repair_invalid_rate=invalid_after / cases,
        rubric_graded=rubric_graded,
        rubric_passed=rubric_passed,
        rubric_pass_rate=(rubric_passed / rubric_graded) if rubric_graded else None,
    )


def aggregate_calls(calls: Sequence[LlmCallLog]) -> dict[str, CallAggregates]:
    """Per-node latency/token/cost aggregates from observability records.

    Axiom 22: latency and cost are *read from observability records*, never
    re-measured by the harness."""
    by_node: dict[str, list[LlmCallLog]] = {}
    for call in calls:
        by_node.setdefault(call.node.value, []).append(call)
    return {
        node: CallAggregates(
            calls=len(rows),
            total_input_tokens=sum(r.input_tokens for r in rows),
            total_output_tokens=sum(r.output_tokens for r in rows),
            total_cost_estimate_usd=sum(r.cost_estimate_usd for r in rows),
            mean_latency_ms=sum(r.latency_ms for r in rows) / len(rows),
        )
        for node, rows in sorted(by_node.items())
    }


def grade_recording(
    eval_set: EvalSet,
    recording: EvalRecording,
    calls: Sequence[LlmCallLog] = (),
) -> EvalReport:
    """Grade one recording against the eval set. Pure and deterministic.

    Every case must have a recorded attempt list and vice versa — a missing or
    unknown ``case_id`` is an :class:`EvalError`, never a silent skip."""
    case_ids = {case.case_id for case in eval_set.cases}
    recorded_ids = set(recording.outputs)
    if missing := sorted(case_ids - recorded_ids):
        raise EvalError(f"recording has no outputs for cases: {missing}")
    if unknown := sorted(recorded_ids - case_ids):
        raise EvalError(f"recording has outputs for unknown cases: {unknown}")

    grades = [_grade_case(case, recording.outputs[case.case_id]) for case in eval_set.cases]
    by_node: dict[str, list[_CaseGrade]] = {}
    for grade in grades:
        by_node.setdefault(grade.node.value, []).append(grade)

    return EvalReport(
        eval_set_version=eval_set.eval_set_version,
        prompt_version=recording.prompt_version,
        model_name=recording.model_name,
        per_node={node: _metrics_from_grades(g) for node, g in sorted(by_node.items())},
        overall=_metrics_from_grades(grades),
        call_aggregates=aggregate_calls(calls),
    )


def threshold_breaches(report: EvalReport, thresholds: EvalThresholds) -> list[str]:
    """Deterministic breach descriptions; empty when within thresholds."""
    breaches: list[str] = []
    rate = report.overall.post_repair_invalid_rate
    if rate > thresholds.max_post_repair_invalid_rate:
        breaches.append(
            f"post_repair_invalid_rate {rate:.4f} exceeds "
            f"max {thresholds.max_post_repair_invalid_rate:.4f} (axiom 09 target)"
        )
    return breaches


def _rate_comparisons(before: NodeMetrics, after: NodeMetrics) -> list[RateComparison]:
    pairs: list[tuple[str, float | None, float | None]] = [
        ("schema_validity_rate", before.schema_validity_rate, after.schema_validity_rate),
        ("repair_recovery_rate", before.repair_recovery_rate, after.repair_recovery_rate),
        (
            "post_repair_invalid_rate",
            before.post_repair_invalid_rate,
            after.post_repair_invalid_rate,
        ),
        ("rubric_pass_rate", before.rubric_pass_rate, after.rubric_pass_rate),
    ]
    return [
        RateComparison(
            metric=metric,
            before=b,
            after=a,
            delta=(a - b) if a is not None and b is not None else None,
        )
        for metric, b, a in pairs
    ]


def compare_reports(before: EvalReport, after: EvalReport) -> EvalComparison:
    """Before/after report for a prompt or model change (axiom 22).

    Refuses to compare reports from different eval-set versions — the rates
    would not be measuring the same thing."""
    if before.eval_set_version != after.eval_set_version:
        raise EvalError(
            f"cannot compare across eval sets: {before.eval_set_version!r} "
            f"vs {after.eval_set_version!r}"
        )
    shared_nodes = sorted(set(before.per_node) & set(after.per_node))
    return EvalComparison(
        eval_set_version=before.eval_set_version,
        before_prompt_version=before.prompt_version,
        after_prompt_version=after.prompt_version,
        before_model_name=before.model_name,
        after_model_name=after.model_name,
        overall=_rate_comparisons(before.overall, after.overall),
        per_node={
            node: _rate_comparisons(before.per_node[node], after.per_node[node])
            for node in shared_nodes
        },
    )
