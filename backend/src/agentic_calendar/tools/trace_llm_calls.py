"""Render the LLM call trace for a ``run_id`` (operator CLI, module-only).

Usage::

    uv run python -m agentic_calendar.tools.trace_llm_calls \
        --calls calls.json [--run-id run_smoke_001]

``--calls`` is a JSON list of ``llm_call_log`` rows — e.g. the file written
by ``llm_smoke --calls-out``. Without ``--run-id`` the tool lists the run ids
present in the file. With it, the calls for that run render in order with
prompt version, tokens, latency, and validation outcome per call (axiom 22).

Privacy: rows carry hashes and counts only (the contract forbids raw
content), so the trace structurally cannot leak prompts, responses, or
calendar text. Cost figures are deterministic estimates (axiom 09).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from pydantic import ValidationError

from agentic_calendar.llm_nodes.call_log import LlmCallLog

_DISCLOSURE = "Costs are deterministic estimates pending measurement (axiom 09)."


def _load_calls(path: Path) -> list[LlmCallLog]:
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"{path} must contain a JSON list of llm_call_log rows")
    return [LlmCallLog.model_validate(row) for row in data]


def _print_run_index(calls: Sequence[LlmCallLog]) -> None:
    counts: dict[str, int] = {}
    for call in calls:
        counts[call.run_id] = counts.get(call.run_id, 0) + 1
    print(f"{len(calls)} calls across {len(counts)} run(s); pass --run-id to trace one:")
    for run_id, count in sorted(counts.items()):
        print(f"  {run_id}  ({count} calls)")


def _print_trace(run_id: str, calls: Sequence[LlmCallLog]) -> None:
    print(f"LLM call trace for run_id={run_id} ({len(calls)} calls)")
    for index, call in enumerate(calls, 1):
        reason = call.reason_code.value if call.reason_code is not None else "-"
        flags = "".join(
            label
            for label, on in (
                (" cache_hit", call.cache_hit),
                (" truncated", call.truncated),
                (" refusal", call.refusal),
            )
            if on
        )
        print(
            f"{index:>3}. {call.node.value:<24} attempt={call.attempt} "
            f"sdk_retry={call.sdk_retry} {call.validation_outcome.value:<4} "
            f"reason={reason}"
        )
        print(
            f"     {call.prompt_version} on {call.model_name} | "
            f"tokens={call.input_tokens}/{call.output_tokens} "
            f"cost=${call.cost_estimate_usd:.4f} latency={call.latency_ms}ms"
            f"{flags}"
        )
    total_cost = sum(c.cost_estimate_usd for c in calls)
    total_in = sum(c.input_tokens for c in calls)
    total_out = sum(c.output_tokens for c in calls)
    failures = sum(1 for c in calls if c.reason_code is not None)
    print(
        f"totals: tokens={total_in}/{total_out} cost=${total_cost:.4f} "
        f"failed_calls={failures}"
    )
    print(_DISCLOSURE)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="trace_llm_calls",
        description="Render the per-run LLM call trace from recorded llm_call_log rows.",
    )
    parser.add_argument(
        "--calls",
        type=Path,
        required=True,
        help="JSON list of llm_call_log rows (e.g. from llm_smoke --calls-out).",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="Run to trace; omit to list the run ids present in the file.",
    )
    args = parser.parse_args(argv)

    try:
        calls = _load_calls(args.calls)
    except (OSError, json.JSONDecodeError, ValidationError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.run_id is None:
        _print_run_index(calls)
        return 0

    run_calls = [c for c in calls if c.run_id == args.run_id]
    if not run_calls:
        print(f"error: no calls recorded for run_id={args.run_id!r}", file=sys.stderr)
        return 1
    _print_trace(args.run_id, run_calls)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
