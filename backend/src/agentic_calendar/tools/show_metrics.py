"""Compute and display telemetry metrics from a JSON file.

Reads a JSON file with an ``events`` key containing a list of telemetry
payloads. Validates each payload as a :class:`TelemetryEvent`, then computes
and prints the :class:`MetricsReport` fields.

Usage::

    uv run python -m agentic_calendar.tools.show_metrics events.json
    uv run python -m agentic_calendar.tools.show_metrics events.json --json
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from agentic_calendar.contracts.telemetry import TelemetryEvent
from agentic_calendar.telemetry.metrics import MetricsReport


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Compute telemetry metrics from a JSON file with an 'events' key."
        )
    )
    parser.add_argument(
        "file",
        type=Path,
        help="Path to JSON file containing {\"events\": [...]}.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="emit_json",
        help="Emit the report as JSON instead of human-readable text.",
    )
    args = parser.parse_args(argv)

    try:
        raw_text = args.file.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"error: cannot read {args.file}: {exc}", file=sys.stderr)
        return 1

    try:
        data: Any = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        print(f"error: invalid JSON in {args.file}: {exc}", file=sys.stderr)
        return 1

    if not isinstance(data, dict):
        print(
            f"error: expected a JSON object with an 'events' key, got {type(data).__name__}",
            file=sys.stderr,
        )
        return 1

    raw_events = data.get("events")
    if not isinstance(raw_events, list):
        print(
            "error: 'events' key must be a JSON array",
            file=sys.stderr,
        )
        return 1

    events: list[TelemetryEvent] = []
    for i, raw in enumerate(raw_events):
        try:
            events.append(TelemetryEvent.model_validate(raw))
        except ValidationError as exc:
            tid = raw.get("telemetry_event_id", f"<index {i}>") if isinstance(raw, dict) else f"<index {i}>"
            print(f"error: invalid telemetry event [{tid}]: {exc}", file=sys.stderr)
            return 1

    report = MetricsReport.from_events(events)

    if args.emit_json:
        print(json.dumps(dataclasses.asdict(report), indent=2))
    else:
        print(f"sample_size:           {report.sample_size}")
        print(f"completed_count:       {report.completed_count}")
        print(f"completion_rate:       {report.completion_rate:.4f}")
        if report.median_duration_error is None:
            print("median_duration_error: None")
        else:
            print(f"median_duration_error: {report.median_duration_error:.4f}")
        print(f"schedule_edit_rate:    {report.schedule_edit_rate:.4f}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
