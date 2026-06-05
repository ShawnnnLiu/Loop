"""Ingest one or more telemetry payloads from a JSON file.

Accepts a single telemetry payload object or a list of them. For each payload
the ingestion result (ingested / duplicate / rejected) is printed on its own
line. Exits non-zero if any payload was rejected.

Usage::

    uv run python -m agentic_calendar.tools.ingest_telemetry payloads.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from agentic_calendar.common.clock import SystemClock
from agentic_calendar.telemetry.event_store import InMemoryTelemetryEventStore
from agentic_calendar.telemetry.ingestion import IngestionStatus, TelemetryIngestor


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Ingest telemetry payload(s) from a JSON file. "
            "The file may contain a single payload object or a list of them."
        )
    )
    parser.add_argument(
        "file",
        type=Path,
        help="Path to JSON file containing one payload or a list of payloads.",
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

    if isinstance(data, dict):
        payloads: list[Any] = [data]
    elif isinstance(data, list):
        payloads = data
    else:
        print(
            f"error: expected a JSON object or array, got {type(data).__name__}",
            file=sys.stderr,
        )
        return 1

    store = InMemoryTelemetryEventStore()
    ingestor = TelemetryIngestor(clock=SystemClock(), store=store)

    any_rejected = False
    for i, payload in enumerate(payloads):
        if not isinstance(payload, dict):
            print(
                f"[{i}] rejected — expected object, got {type(payload).__name__}",
            )
            any_rejected = True
            continue

        outcome = ingestor.ingest(payload)
        tid = payload.get("telemetry_event_id", f"<index {i}>")
        if outcome.status is IngestionStatus.REJECTED:
            any_rejected = True
            print(
                f"[{tid}] rejected"
                f" reason_code={outcome.reason_code}"
                f" error={outcome.error!r}"
            )
        elif outcome.status is IngestionStatus.DUPLICATE:
            print(f"[{tid}] duplicate")
        else:
            print(f"[{tid}] ingested")

    return 1 if any_rejected else 0


if __name__ == "__main__":
    raise SystemExit(main())
