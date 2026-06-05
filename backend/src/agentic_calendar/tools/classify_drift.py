"""Classify plan drift from telemetry and plan data.

Reads a JSON file with required keys ``plan`` (a TaskPlan) and ``events``
(list of telemetry payloads), and optional keys ``weekly_cycles``,
``fragmentation``, and ``external_conflict_task_ids``.

Runs the deterministic :class:`DriftClassifier` and prints each drift event
or "no drift detected" if none fired.

Usage::

    uv run python -m agentic_calendar.tools.classify_drift input.json
    uv run python -m agentic_calendar.tools.classify_drift input.json --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from agentic_calendar.common.clock import SystemClock
from agentic_calendar.common.ids import UuidIdGenerator
from agentic_calendar.contracts.task_plan import TaskPlan
from agentic_calendar.contracts.telemetry import TelemetryEvent
from agentic_calendar.drift import (
    DriftClassifier,
    DriftInput,
    FragmentationSignal,
    WeeklyCapacity,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Classify plan drift from a JSON file containing 'plan' and 'events' keys."
        )
    )
    parser.add_argument(
        "file",
        type=Path,
        help=(
            "Path to JSON file with keys: plan (TaskPlan), events (list), "
            "and optional: weekly_cycles, fragmentation, external_conflict_task_ids."
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="emit_json",
        help="Emit drift events as JSON instead of human-readable text.",
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
            f"error: expected a JSON object, got {type(data).__name__}",
            file=sys.stderr,
        )
        return 1

    # Validate plan
    if "plan" not in data:
        print("error: input file must contain a 'plan' key", file=sys.stderr)
        return 1
    try:
        plan = TaskPlan.model_validate(data["plan"])
    except ValidationError as exc:
        print(f"error: invalid task plan: {exc}", file=sys.stderr)
        return 1

    # Validate events
    raw_events = data.get("events", [])
    if not isinstance(raw_events, list):
        print("error: 'events' key must be a JSON array", file=sys.stderr)
        return 1
    events: list[TelemetryEvent] = []
    for i, raw in enumerate(raw_events):
        try:
            events.append(TelemetryEvent.model_validate(raw))
        except ValidationError as exc:
            tid = (
                raw.get("telemetry_event_id", f"<index {i}>")
                if isinstance(raw, dict)
                else f"<index {i}>"
            )
            print(f"error: invalid telemetry event [{tid}]: {exc}", file=sys.stderr)
            return 1

    # Optional: weekly_cycles
    weekly_cycles: list[WeeklyCapacity] = []
    for i, c in enumerate(data.get("weekly_cycles", [])):
        try:
            weekly_cycles.append(WeeklyCapacity(**c))
        except (TypeError, ValueError) as exc:
            print(
                f"error: invalid weekly_cycle[{i}]: {exc}", file=sys.stderr
            )
            return 1

    # Optional: fragmentation
    fragmentation: FragmentationSignal | None = None
    if frag_raw := data.get("fragmentation"):
        try:
            fragmentation = FragmentationSignal(**frag_raw)
        except (TypeError, ValueError) as exc:
            print(f"error: invalid fragmentation signal: {exc}", file=sys.stderr)
            return 1

    # Optional: external_conflict_task_ids
    external_conflict_task_ids: frozenset[str] = frozenset(
        data.get("external_conflict_task_ids", [])
    )

    clf = DriftClassifier(clock=SystemClock(), id_generator=UuidIdGenerator())
    drift_events = clf.classify(
        DriftInput(
            plan=plan,
            events=events,
            weekly_cycles=weekly_cycles,
            fragmentation=fragmentation,
            external_conflict_task_ids=external_conflict_task_ids,
        )
    )

    if not drift_events:
        print("no drift detected")
        return 0

    if args.emit_json:
        print(json.dumps([e.model_dump(mode="json") for e in drift_events], indent=2))
    else:
        for de in drift_events:
            ev = de.evidence
            print(
                f"drift_type={de.drift_type.value}"
                f"  reason_code={de.reason_code.value}"
                f"  confidence={de.confidence}"
                f"  policy={de.recommended_policy_action.value}"
            )
            print(
                f"  evidence: metric={ev.trigger_metric}"
                f"  value={ev.trigger_value}"
                f"  threshold={ev.threshold}"
                f"  sample_size={ev.sample_size}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
