"""Render the schedule-quality breakdown for a scheduler-input fixture (read-only).

Usage (module-only, like every Phase 7+ CLI)::

    uv run python -m agentic_calendar.tools.show_placement_quality \
        tests/fixtures/placement_quality/five_tasks_three_days.json [--json]

The fixture is a serialized ``SchedulerInput``. The tool runs the pure
``schedule()`` on it and prints the schedule-level scoring breakdown from
``score_schedule`` (axiom 05 "Scored Placement"): per-day load, per-term
totals, and the time-of-day band histogram of placed starts. This is the
before/after evidence surface for placement-quality work — schedule-level
totals, never sums of the path-dependent marginal values.

Strictly read-only and offline: no store, no clock, no calendar — the
Scheduler is a pure function and this tool only prints its output. Weights
are the ``PlacementScoringConfig`` defaults (heuristic priors, axiom 07);
serving overrides come from ``tuning.toml`` through the composition root,
not through this tool.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from agentic_calendar.common.errors import AgenticCalendarError
from agentic_calendar.contracts.placement_evidence import PlacementEvidence
from agentic_calendar.scheduler import schedule
from agentic_calendar.scheduler.inputs import SchedulerInput
from agentic_calendar.scheduler.scoring import (
    ScheduleScoreBreakdown,
    score_schedule,
)

_DISCLOSURE = (
    "All weights are heuristic priors pending calibration (axiom 07); "
    "totals are schedule-level, not marginal sums."
)

_TERM_FIELDS = (
    "daily_balance_total",
    "back_to_back_total",
    "fragmentation_total",
    "deep_window_conservation_total",
    "earliness_total",
    "evening_preference_total",
    "weekend_long_block_total",
)


def _evidence_applied(evidence: PlacementEvidence) -> list[dict[str, object]]:
    """The input's evidence cells, JSON-shaped — the audit surface that
    makes every band shift explainable by a printed cell (axiom 05)."""
    return [cell.model_dump(mode="json") for cell in evidence.cells]


def _print_human(
    fixture: Path,
    breakdown: ScheduleScoreBreakdown,
    status: str,
    evidence: PlacementEvidence,
) -> None:
    print(f"fixture: {fixture}")
    print(f"schedule_status: {status}")
    print(
        f"scheduled: {breakdown.scheduled_count}"
        f"  unscheduled: {breakdown.unscheduled_count}"
    )
    print(f"target_daily_min: {breakdown.target_daily_min}")
    print("per-day minutes:")
    for day, minutes in sorted(breakdown.per_day_minutes.items()):
        print(f"  {day}  {minutes}")
    print("band histogram (placed starts):")
    for band, count in sorted(breakdown.band_histogram.items()):
        print(f"  {band}  {count}")
    print("evidence applied (input cells; any band shift traces to one):")
    if not evidence.cells:
        print("  (none)")
    for cell in evidence.cells:
        multiplier = "-" if cell.multiplier is None else f"{cell.multiplier}"
        print(
            f"  {cell.category.value}  {cell.time_of_day_band.value}"
            f"  source={cell.source.value}  multiplier={multiplier}"
            f"  weighted_sample={cell.weighted_sample}"
        )
    print("term totals (schedule-level):")
    for field in _TERM_FIELDS:
        print(f"  {field}  {getattr(breakdown, field)}")
    print(f"total_cost: {breakdown.total_cost}")
    print(_DISCLOSURE)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="show_placement_quality",
        description=(
            "Run the pure scheduler on a SchedulerInput fixture and print the "
            "schedule-level placement-quality breakdown."
        ),
    )
    parser.add_argument(
        "fixture", type=Path, help="path to a serialized SchedulerInput JSON"
    )
    parser.add_argument("--json", action="store_true", help="emit one JSON document")
    args = parser.parse_args(argv)

    try:
        inp = SchedulerInput.model_validate_json(
            args.fixture.read_text(encoding="utf-8")
        )
    except (AgenticCalendarError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    output = schedule(inp)
    breakdown = score_schedule(output, inp)
    if args.json:
        print(
            json.dumps(
                {
                    "fixture": str(args.fixture),
                    "schedule_status": output.schedule_status.value,
                    "breakdown": dataclasses.asdict(breakdown),
                    "evidence_applied": _evidence_applied(inp.placement_evidence),
                },
                indent=2,
            )
        )
        return 0
    _print_human(
        args.fixture, breakdown, output.schedule_status.value, inp.placement_evidence
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
