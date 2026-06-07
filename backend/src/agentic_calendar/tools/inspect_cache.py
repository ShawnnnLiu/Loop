"""Inspect cache entries and report each one's live/stale status (axiom 18).

A composition-root demo: it wires the cache's :func:`is_entry_valid` to a
source-claim registry. Reads a JSON file with ``claims`` (the source claims that
form the registry) and ``entries`` (cache entries), and given ``--now`` reports
for each entry whether every justifying claim is present and live, or stale
(missing / expired / contradicted evidence).

Like the other Phase 4+ operator tools, this is invoked as a module (it is not
registered as a console script).

Usage::

    uv run python -m agentic_calendar.tools.inspect_cache cache.json \\
        --now 2026-06-04T12:00:00+00:00
    uv run python -m agentic_calendar.tools.inspect_cache cache.json \\
        --now 2026-06-04T12:00:00+00:00 --json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from agentic_calendar.cache.invalidation import is_entry_valid
from agentic_calendar.cache.store import CacheEntry
from agentic_calendar.contracts.source_claim import SourceClaim
from agentic_calendar.source_claims.ingestion import InMemorySourceClaimStore


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Report cache entries' live/stale status against a claim registry."
        )
    )
    parser.add_argument(
        "file",
        type=Path,
        help='JSON file: {"claims": [...], "entries": [...]}.',
    )
    parser.add_argument(
        "--now",
        required=True,
        help="ISO-8601 timezone-aware instant for the liveness check.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="emit_json",
        help="Emit the report as JSON instead of human-readable text.",
    )
    args = parser.parse_args(argv)

    try:
        now = datetime.fromisoformat(args.now)
    except ValueError as exc:
        print(f"error: invalid --now: {exc}", file=sys.stderr)
        return 1
    if now.tzinfo is None:
        print("error: --now must be timezone-aware", file=sys.stderr)
        return 1

    try:
        data: Any = json.loads(args.file.read_text(encoding="utf-8"))
    except OSError as exc:
        print(f"error: cannot read {args.file}: {exc}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as exc:
        print(f"error: invalid JSON in {args.file}: {exc}", file=sys.stderr)
        return 1
    if not isinstance(data, dict):
        print(
            "error: expected a JSON object with 'claims' and 'entries' keys",
            file=sys.stderr,
        )
        return 1

    registry = InMemorySourceClaimStore()
    claims_raw = data.get("claims", [])
    if not isinstance(claims_raw, list):
        print("error: 'claims' must be a JSON array", file=sys.stderr)
        return 1
    for i, raw in enumerate(claims_raw):
        try:
            claim = SourceClaim.model_validate(raw)
        except ValidationError as exc:
            print(f"error: invalid claim [index {i}]: {exc}", file=sys.stderr)
            return 1
        if not registry.exists(claim.claim_id):
            registry.append(claim)

    entries_raw = data.get("entries", [])
    if not isinstance(entries_raw, list):
        print("error: 'entries' must be a JSON array", file=sys.stderr)
        return 1

    rows: list[dict[str, Any]] = []
    for i, raw in enumerate(entries_raw):
        try:
            entry = CacheEntry.model_validate(raw)
        except ValidationError as exc:
            print(f"error: invalid cache entry [index {i}]: {exc}", file=sys.stderr)
            return 1
        live = is_entry_valid(entry, now=now, registry=registry)
        rows.append(
            {
                "fingerprint": entry.key.fingerprint(),
                "target": entry.value_kind.value,
                "source_claim_ids": list(entry.source_claim_ids),
                "status": "live" if live else "stale",
            }
        )

    if args.emit_json:
        print(json.dumps(rows, indent=2))
    else:
        if not rows:
            print("(no cache entries)")
        for row in rows:
            print(
                f"{row['status']:5}  {row['target']:24}  "
                f"{row['fingerprint'][:23]}  claims={row['source_claim_ids']}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
