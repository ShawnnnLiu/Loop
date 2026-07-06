"""Capture REAL eval recordings from the live adapters (UX pass C2).

Usage::

    # Offline: parse + contract-validate every case's inputs, no network.
    uv run python -m agentic_calendar.tools.capture_eval_recordings \
        --eval-set evalsets/eval_set_v2.json --validate-only

    # Live (networked; requires ANTHROPIC_API_KEY and --live):
    uv run python -m agentic_calendar.tools.capture_eval_recordings \
        --eval-set evalsets/eval_set_v2.json \
        --out evalsets/recordings/baseline_2026_07_04.json \
        --label baseline-2026-07-04 --live [--judge]

Why this exists: the only committed recordings were synthetic fixtures, so
every rate the eval harness produced proved the harness, not the prompts
(axiom 22's honesty rule). This tool runs each eval case through the REAL
adapters — production configs, production prompts, the same bounded repair
loop — and records the raw per-attempt outputs via the engine's
``attempt_recorder`` hook, producing an :class:`EvalRecording` that
``run_llm_eval`` grades offline forever after.

Safeguards mirror ``llm_smoke``: live calls require BOTH ``--live`` and the
key; every call passes through the same guarded transport (hard call cap
sized to the set, cumulative cost ceiling derived from the configured output
caps); at most the bounded 2 SDK retries + 2 repairs per case. ``--judge``
adds one Tier-2 judge call per valid prose output (advisory scores only).
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from agentic_calendar.common.clock import SystemClock
from agentic_calendar.common.ids import UuidIdGenerator
from agentic_calendar.contracts.drift_event import DriftEvent
from agentic_calendar.contracts.source_claim import SourceClaim
from agentic_calendar.contracts.strategy_constraints import StrategyConstraints
from agentic_calendar.contracts.syllabus_units import SyllabusUnits
from agentic_calendar.contracts.user_profile import UserProfile
from agentic_calendar.contracts.validation_result import ValidationResult
from agentic_calendar.llm_nodes import (
    AnthropicMessagesTransport,
    AnthropicPlanner,
    AnthropicReflectionSummary,
    AnthropicStrategist,
    AnthropicTransport,
    AnthropicUserFacingExplanation,
    InMemoryLlmCallLogStore,
    LLMNodeError,
)
from agentic_calendar.llm_nodes.anthropic_adapter import (
    EXPLANATION_CONFIG,
    PLANNER_CONFIG,
    REFLECTION_CONFIG,
    STRATEGIST_CONFIG,
)
from agentic_calendar.llm_nodes.call_log import LlmNodeName
from agentic_calendar.llm_nodes.eval import EvalCase, EvalRecording, EvalSet
from agentic_calendar.llm_nodes.eval_judge import JUDGE_CONFIG, judge_recording
from agentic_calendar.tools.llm_smoke import SmokeGuardTripped, _GuardedTransport

_NODE_CONFIGS = {
    LlmNodeName.STRATEGIST: STRATEGIST_CONFIG,
    LlmNodeName.PLANNER: PLANNER_CONFIG,
    LlmNodeName.REFLECTION_SUMMARY: REFLECTION_CONFIG,
    LlmNodeName.USER_FACING_EXPLANATION: EXPLANATION_CONFIG,
}

#: Headroom multiplier over one clean pass at each case's output cap — covers
#: the input-token heuristic plus bounded repair re-prompts.
_COST_BUDGET_OVERHEAD = 2.0


class CaptureInputError(Exception):
    """An eval case's inputs are missing or fail contract validation."""


def _resolve_profile(
    case: EvalCase, inputs: Mapping[str, Any], by_id: Mapping[str, EvalCase]
) -> UserProfile | None:
    """``user_profile`` inline, or ``user_profile_ref`` naming another case
    whose inputs carry the profile (keeps the set free of 40-line repeats)."""
    if "user_profile" in inputs:
        return UserProfile.model_validate(inputs["user_profile"])
    ref = inputs.get("user_profile_ref")
    if ref is None:
        return None
    referenced = by_id.get(str(ref))
    if referenced is None or "user_profile" not in referenced.inputs:
        raise CaptureInputError(
            f"case {case.case_id!r}: user_profile_ref {ref!r} does not name a "
            f"case with an inline user_profile"
        )
    return UserProfile.model_validate(referenced.inputs["user_profile"])


def parse_case_inputs(
    case: EvalCase, by_id: Mapping[str, EvalCase]
) -> dict[str, Any]:
    """Contract-validate one case's inputs into the node's run() kwargs."""
    inputs = case.inputs
    if not inputs:
        raise CaptureInputError(
            f"case {case.case_id!r} has no inputs — recordings must come from "
            f"the real prompts (axiom 22); extend the eval set first"
        )
    if case.node is LlmNodeName.STRATEGIST:
        profile = _resolve_profile(case, inputs, by_id)
        if profile is None:
            raise CaptureInputError(f"case {case.case_id!r}: strategist needs a user_profile")
        kwargs: dict[str, Any] = {
            "user_profile": profile,
            "source_claims": [
                SourceClaim.model_validate(claim)
                for claim in inputs.get("source_claims", [])
            ],
        }
        if "strategy_constraints" in inputs:
            kwargs["strategy_constraints"] = StrategyConstraints.model_validate(
                inputs["strategy_constraints"]
            )
        return kwargs
    if case.node is LlmNodeName.PLANNER:
        return {
            "syllabus": SyllabusUnits.model_validate(inputs["syllabus"]),
            "plan_version": str(inputs.get("plan_version", f"plan_{case.case_id}")),
            "user_profile": _resolve_profile(case, inputs, by_id),
            "excluded_tasks": [str(t) for t in inputs.get("excluded_tasks", [])],
        }
    if case.node is LlmNodeName.REFLECTION_SUMMARY:
        return {
            "drift_events": [
                DriftEvent.model_validate(event)
                for event in inputs.get("drift_events", [])
            ],
            "completion_rate": inputs.get("completion_rate"),
        }
    return {
        "validation_result": ValidationResult.model_validate(inputs["validation_result"]),
    }


def _adapter_for(
    node: LlmNodeName,
    transport: AnthropicTransport,
    store: InMemoryLlmCallLogStore,
    recorder: Any,
) -> Any:
    common = {
        "transport": transport,
        "store": store,
        "clock": SystemClock(),
        "id_generator": UuidIdGenerator(),
        "attempt_recorder": recorder,
    }
    if node is LlmNodeName.STRATEGIST:
        return AnthropicStrategist(**common)
    if node is LlmNodeName.PLANNER:
        return AnthropicPlanner(**common)
    if node is LlmNodeName.REFLECTION_SUMMARY:
        return AnthropicReflectionSummary(**common)
    return AnthropicUserFacingExplanation(**common)


def capture(
    eval_set: EvalSet,
    *,
    transport: AnthropicTransport,
    store: InMemoryLlmCallLogStore,
    label: str,
) -> EvalRecording:
    """Run every case through its real adapter, recording raw attempts.

    A case whose generation exhausts the bounded loop still records its
    invalid attempts — that IS the signal the repair-recovery rate measures.
    A case that produced no parseable output at all records ``[{}]`` so
    grading counts it invalid rather than silently missing.
    """
    by_id = {case.case_id: case for case in eval_set.cases}
    outputs: dict[str, list[dict[str, Any]]] = {}
    for case in eval_set.cases:
        kwargs = parse_case_inputs(case, by_id)
        attempts: dict[int, dict[str, Any] | None] = {}

        def record(attempt: int, payload: dict[str, Any] | None) -> None:
            attempts[attempt] = payload  # noqa: B023 — rebound per case below

        adapter = _adapter_for(case.node, transport, store, record)
        # A generation failure is expected for repair-prone cases: the
        # recorded invalid attempts are exactly what the eval measures.
        # Guard trips are NOT suppressed — they must abort the capture.
        with contextlib.suppress(LLMNodeError):
            adapter.run(run_id=f"eval_{case.case_id}", **kwargs)
        outputs[case.case_id] = [
            attempts.get(i) or {} for i in sorted(attempts)
        ] or [{}]
        print(
            f"  {case.case_id}: {len(outputs[case.case_id])} attempt(s) recorded",
            file=sys.stderr,
        )
    model_name = "+".join(
        sorted({config.model_name for config in _NODE_CONFIGS.values()})
    )
    return EvalRecording(prompt_version=label, model_name=model_name, outputs=outputs)


def _default_budget(eval_set: EvalSet) -> float:
    per_case_output_cost = sum(
        _NODE_CONFIGS[case.node].max_tokens
        * _NODE_CONFIGS[case.node].output_price_per_mtok
        for case in eval_set.cases
    ) / 1_000_000
    return round(per_case_output_cost * _COST_BUDGET_OVERHEAD, 2)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Capture real eval recordings from the live adapters."
    )
    parser.add_argument("--eval-set", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--label", default=None, help="Recording label (prompt_version).")
    parser.add_argument("--live", action="store_true", help="Allow real API calls.")
    parser.add_argument("--judge", action="store_true", help="Add Tier-2 judge scores.")
    parser.add_argument("--max-cost-usd", type=float, default=None)
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Parse + contract-validate every case's inputs; no network.",
    )
    args = parser.parse_args(argv)

    eval_set = EvalSet.model_validate(json.loads(args.eval_set.read_text()))
    by_id = {case.case_id: case for case in eval_set.cases}

    try:
        for case in eval_set.cases:
            parse_case_inputs(case, by_id)
    except CaptureInputError as exc:
        print(f"invalid eval set: {exc}", file=sys.stderr)
        return 1
    print(f"{len(eval_set.cases)} case inputs validated", file=sys.stderr)
    if args.validate_only:
        return 0

    if not args.live or not os.environ.get("ANTHROPIC_API_KEY"):
        print(
            "live capture requires BOTH --live and ANTHROPIC_API_KEY "
            "(networked command; run it deliberately)",
            file=sys.stderr,
        )
        return 1
    if args.out is None or args.label is None:
        print("--out and --label are required for a live capture", file=sys.stderr)
        return 1

    prose_cases = sum(
        1
        for case in eval_set.cases
        if case.node
        in (LlmNodeName.REFLECTION_SUMMARY, LlmNodeName.USER_FACING_EXPLANATION)
    )
    max_calls = len(eval_set.cases) * 3 + (prose_cases * 3 if args.judge else 0)
    budget = args.max_cost_usd if args.max_cost_usd is not None else _default_budget(eval_set)
    pricing = {
        config.model_name: (config.input_price_per_mtok, config.output_price_per_mtok)
        for config in (*_NODE_CONFIGS.values(), JUDGE_CONFIG)
    }
    store = InMemoryLlmCallLogStore()
    transport = _GuardedTransport(
        AnthropicMessagesTransport(),
        store=store,
        max_calls=max_calls,
        max_cost_usd=budget,
        pricing=pricing,
    )

    try:
        recording = capture(eval_set, transport=transport, store=store, label=args.label)
        if args.judge:
            scores, unjudged = judge_recording(
                eval_set, recording, transport=transport
            )
            recording = EvalRecording(
                prompt_version=recording.prompt_version,
                model_name=recording.model_name,
                outputs=recording.outputs,
                judge_scores=scores,
            )
            if unjudged:
                print(f"judge could not score: {unjudged}", file=sys.stderr)
    except SmokeGuardTripped as exc:
        print(f"aborted by guard: {exc}", file=sys.stderr)
        return 2

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(recording.model_dump_json(indent=2) + "\n", encoding="utf-8")
    spent = sum(row.cost_estimate_usd for row in store.list_all())
    print(
        f"wrote {args.out} ({transport.calls} calls, ~${spent:.4f} estimated)",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
