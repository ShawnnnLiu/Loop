"""Run the LLM eval harness over a recorded output set.

Operator CLI (module-only, like ``show_accountability``)::

    uv run python -m agentic_calendar.tools.run_llm_eval \
        --eval-set evalsets/eval_set_v1.json \
        --recording evalsets/recordings/fixture_baseline.json \
        [--calls calls.json] [--out report.json] [--compare baseline_report.json]

The CLI is deterministic and fully offline: it grades *recorded* outputs
against the deterministic contracts and reports aggregate rates against
thresholds (axiom 22). It never calls a model. By default breaches are
printed and the exit stays 0; with ``--strict`` a breach exits 3 — the
amended axiom 22 lets deterministic RECORDED-output grading gate merges
(live-call evals still never run in CI).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from agentic_calendar.llm_nodes.call_log import LlmCallLog
from agentic_calendar.llm_nodes.eval import (
    EvalComparison,
    EvalError,
    EvalRecording,
    EvalReport,
    EvalSet,
    EvalThresholds,
    compare_reports,
    grade_recording,
    threshold_breaches,
)

_DISCLOSURE = (
    "Note: rates measure recorded outputs against contracts; recordings of "
    "fixtures prove the harness, not live model quality (axiom 09 disclosure)."
)


def _load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _fmt_rate(value: float | None) -> str:
    return f"{value:.4f}" if value is not None else "n/a"


def _print_report(report: EvalReport, thresholds: EvalThresholds) -> None:
    print("LLM eval report")
    print(f"  eval_set_version: {report.eval_set_version}")
    print(f"  prompt_version:   {report.prompt_version}")
    print(f"  model_name:       {report.model_name}")
    print()
    header = (
        f"  {'node':<26} {'cases':>5} {'validity':>9} {'recovery':>9} "
        f"{'post-invalid':>12} {'rubric':>7}"
    )
    print(header)
    rows = [("overall", report.overall), *sorted(report.per_node.items())]
    for name, m in rows:
        print(
            f"  {name:<26} {m.cases:>5} {_fmt_rate(m.schema_validity_rate):>9} "
            f"{_fmt_rate(m.repair_recovery_rate):>9} "
            f"{_fmt_rate(m.post_repair_invalid_rate):>12} "
            f"{_fmt_rate(m.rubric_pass_rate):>7}"
        )
    if report.call_aggregates:
        print()
        print("  call aggregates (from llm_call_log records)")
        for node, agg in sorted(report.call_aggregates.items()):
            print(
                f"  {node:<26} calls={agg.calls} in_tok={agg.total_input_tokens} "
                f"out_tok={agg.total_output_tokens} "
                f"cost=${agg.total_cost_estimate_usd:.4f} "
                f"mean_latency={agg.mean_latency_ms:.0f}ms"
            )
    if report.grounding is not None:
        g = report.grounding
        print()
        print(
            f"  grounding (tier-1): {g.cases_with_claims} grounded / "
            f"{g.cases_without_claims} ungrounded strategist case(s)"
        )
        print(
            f"    citation_coverage={_fmt_rate(g.citation_coverage)} "
            f"claim_utilization={_fmt_rate(g.claim_utilization)} "
            f"high_confidence_share={_fmt_rate(g.high_confidence_share)} "
            f"unknown_citations={g.unknown_citation_count}"
        )
    if report.groundedness_scores:
        scores = ", ".join(
            f"{case_id}={score.groundedness}"
            for case_id, score in sorted(report.groundedness_scores.items())
        )
        print(f"  groundedness (tier-2, advisory): {scores}")
    print()
    breaches = threshold_breaches(report, thresholds)
    if breaches:
        for breach in breaches:
            print(f"THRESHOLD BREACH: {breach}")
    else:
        print("All thresholds satisfied.")
    print(_DISCLOSURE)


def _print_comparison(comparison: EvalComparison) -> None:
    print()
    print(
        f"Before/after (eval set {comparison.eval_set_version}): "
        f"{comparison.before_prompt_version}/{comparison.before_model_name}"
        f" -> {comparison.after_prompt_version}/{comparison.after_model_name}"
    )
    for rc in comparison.overall:
        delta = f"{rc.delta:+.4f}" if rc.delta is not None else "n/a"
        print(
            f"  overall {rc.metric}: {_fmt_rate(rc.before)} -> "
            f"{_fmt_rate(rc.after)} (delta {delta})"
        )
    for node, rcs in sorted(comparison.per_node.items()):
        for rc in rcs:
            delta = f"{rc.delta:+.4f}" if rc.delta is not None else "n/a"
            print(
                f"  {node} {rc.metric}: {_fmt_rate(rc.before)} -> "
                f"{_fmt_rate(rc.after)} (delta {delta})"
            )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="run_llm_eval",
        description="Grade a recorded LLM output set against the eval set (offline).",
    )
    parser.add_argument("--eval-set", type=Path, required=True, help="EvalSet JSON file.")
    parser.add_argument(
        "--recording", type=Path, required=True, help="EvalRecording JSON file."
    )
    parser.add_argument(
        "--calls",
        type=Path,
        default=None,
        help="Optional JSON list of LlmCallLog rows for latency/token/cost aggregates.",
    )
    parser.add_argument(
        "--out", type=Path, default=None, help="Write the report as canonical JSON."
    )
    parser.add_argument(
        "--compare",
        type=Path,
        default=None,
        help="A previously written report JSON to compare this run against (before -> after).",
    )
    parser.add_argument(
        "--max-post-repair-invalid-rate",
        type=float,
        default=0.05,
        help="Alert threshold; axiom 09 target is 0.05.",
    )
    parser.add_argument(
        "--min-schema-validity-rate",
        type=float,
        default=None,
        help="Floor on first-attempt validity (off unless set; seed from a baseline).",
    )
    parser.add_argument(
        "--min-repair-recovery-rate",
        type=float,
        default=None,
        help="Floor on repair recovery (off unless set; seed from a baseline).",
    )
    parser.add_argument(
        "--min-citation-coverage",
        type=float,
        default=None,
        help="Floor on grounded-arm Tier-1 citation coverage (off unless set; "
        "seed from a grounded baseline).",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit 3 on any threshold breach (the recorded-output CI gate).",
    )
    args = parser.parse_args(argv)

    try:
        eval_set = EvalSet.model_validate(_load_json(args.eval_set))
        recording = EvalRecording.model_validate(_load_json(args.recording))
        calls = (
            [LlmCallLog.model_validate(row) for row in _load_json(args.calls)]
            if args.calls is not None
            else []
        )
        report = grade_recording(eval_set, recording, calls)
        thresholds = EvalThresholds(
            max_post_repair_invalid_rate=args.max_post_repair_invalid_rate,
            min_schema_validity_rate=args.min_schema_validity_rate,
            min_repair_recovery_rate=args.min_repair_recovery_rate,
            min_citation_coverage=args.min_citation_coverage,
        )
    except (OSError, json.JSONDecodeError, ValidationError, EvalError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    _print_report(report, thresholds)

    if args.compare is not None:
        try:
            before = EvalReport.model_validate(_load_json(args.compare))
            comparison = compare_reports(before, report)
        except (OSError, json.JSONDecodeError, ValidationError, EvalError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        _print_comparison(comparison)

    if args.out is not None:
        text = json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"
        args.out.write_text(text, encoding="utf-8")
        print(f"wrote {args.out}")

    if args.strict and threshold_breaches(report, thresholds):
        return 3

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
