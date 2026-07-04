"""Aggregate view over the LLM call log (operator CLI, module-only; C3).

Usage::

    uv run python -m agentic_calendar.tools.llm_stats --db /path/to/app.db \
        [--since 2026-07-01] [--until 2026-07-31]
    uv run python -m agentic_calendar.tools.llm_stats --calls calls.json

Answers the post-deploy questions that decide UX priorities and were
previously unanswerable without ad-hoc SQL: real p50/p99 latency per node,
repair-round frequency, cost per run, and whether prompt caching actually
hits. Read-only and deterministic. Threshold warnings are PRINTED, never
enforced — this is the observability counterpart of the eval gate; nothing
here feeds runtime routing (axiom 22).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path

from pydantic import ValidationError

from agentic_calendar.llm_nodes.call_log import LlmCallLog, ValidationOutcome

#: Printed-warning thresholds. Heuristic priors until calibrated (like every
#: threshold in the repo); tune them here once real p99 data accumulates.
WARN_P99_LATENCY_MS = 60_000
WARN_COST_PER_RUN_USD = 0.50

_DISCLOSURE = "Costs are deterministic estimates pending measurement (axiom 09)."


def _percentile(sorted_values: Sequence[int], fraction: float) -> int:
    """Nearest-rank percentile over pre-sorted values (deterministic)."""
    if not sorted_values:
        return 0
    rank = max(1, round(fraction * len(sorted_values)))
    return sorted_values[rank - 1]


def _load_calls_json(path: Path) -> list[LlmCallLog]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"{path} must contain a JSON list of llm_call_log rows")
    return [LlmCallLog.model_validate(row) for row in data]


def _within(call: LlmCallLog, since: date | None, until: date | None) -> bool:
    when = call.created_at.astimezone(UTC)
    if since is not None and when < datetime.combine(since, time(0), tzinfo=UTC):
        return False
    return not (
        until is not None
        and when >= datetime.combine(until + timedelta(days=1), time(0), tzinfo=UTC)
    )


def print_stats(calls: Sequence[LlmCallLog]) -> None:
    if not calls:
        print("no calls in range")
        return
    by_node: dict[str, list[LlmCallLog]] = {}
    for call in calls:
        by_node.setdefault(call.node.value, []).append(call)

    header = (
        f"{'node':<26} {'calls':>5} {'pass':>6} {'repair%':>8} {'cache%':>7} "
        f"{'p50ms':>7} {'p99ms':>7} {'cost$':>8}"
    )
    print(header)
    warnings: list[str] = []
    for node, rows in sorted(by_node.items()):
        latencies = sorted(r.latency_ms for r in rows)
        passes = sum(1 for r in rows if r.validation_outcome is ValidationOutcome.PASS)
        repair_rows = sum(1 for r in rows if r.attempt > 0)
        cache_hits = sum(1 for r in rows if r.cache_hit)
        cost = sum(r.cost_estimate_usd for r in rows)
        p99 = _percentile(latencies, 0.99)
        print(
            f"{node:<26} {len(rows):>5} {passes / len(rows):>6.2f} "
            f"{repair_rows / len(rows):>8.2f} {cache_hits / len(rows):>7.2f} "
            f"{_percentile(latencies, 0.50):>7} {p99:>7} {cost:>8.4f}"
        )
        if p99 > WARN_P99_LATENCY_MS:
            warnings.append(
                f"{node}: p99 latency {p99}ms exceeds {WARN_P99_LATENCY_MS}ms"
            )

    runs: dict[str, float] = {}
    for call in calls:
        runs[call.run_id] = runs.get(call.run_id, 0.0) + call.cost_estimate_usd
    total_cost = sum(runs.values())
    mean_cost_per_run = total_cost / len(runs)
    print(
        f"\nruns={len(runs)} total_cost=${total_cost:.4f} "
        f"mean_cost_per_run=${mean_cost_per_run:.4f}"
    )
    if mean_cost_per_run > WARN_COST_PER_RUN_USD:
        warnings.append(
            f"mean cost per run ${mean_cost_per_run:.4f} exceeds "
            f"${WARN_COST_PER_RUN_USD:.2f}"
        )
    for warning in warnings:
        print(f"WARNING (advisory, never enforced): {warning}")
    print(_DISCLOSURE)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="llm_stats",
        description="Per-node validity/repair/latency/cost aggregates from the call log.",
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--db", type=Path, help="Production SQLite database.")
    source.add_argument("--calls", type=Path, help="JSON list of llm_call_log rows.")
    parser.add_argument("--since", type=date.fromisoformat, default=None)
    parser.add_argument("--until", type=date.fromisoformat, default=None)
    args = parser.parse_args(argv)

    try:
        if args.db is not None:
            from agentic_calendar.common.sqlite import SqliteDatabase
            from agentic_calendar.llm_nodes.sqlite_call_log import SqliteLlmCallLogStore

            if not args.db.exists():
                raise OSError(f"database not found: {args.db}")
            calls = SqliteLlmCallLogStore(SqliteDatabase(args.db)).list_all()
        else:
            calls = _load_calls_json(args.calls)
    except (OSError, json.JSONDecodeError, ValidationError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print_stats([c for c in calls if _within(c, args.since, args.until)])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
