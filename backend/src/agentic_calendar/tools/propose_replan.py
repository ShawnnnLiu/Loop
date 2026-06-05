"""Propose a recalibrated plan version from duration multipliers.

Reads a JSON file with keys ``active_plan`` (a PlanVersion) and ``multipliers``
(a UserDurationMultipliers). Runs the deterministic recalibration pass and
prints the draft plan summary, or "no duration change; nothing to recalibrate"
when calibration produces no change.

Usage::

    uv run python -m agentic_calendar.tools.propose_replan input.json
    uv run python -m agentic_calendar.tools.propose_replan input.json --json
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
from agentic_calendar.contracts.user_duration_multipliers import UserDurationMultipliers
from agentic_calendar.planning import PlanVersion, propose_recalibrated_plan


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Propose a recalibrated plan version based on duration multipliers."
        )
    )
    parser.add_argument(
        "file",
        type=Path,
        help=(
            "Path to JSON file with keys: "
            "active_plan (PlanVersion) and multipliers (UserDurationMultipliers)."
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="emit_json",
        help="Emit the diff summary as JSON instead of human-readable text.",
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

    if "active_plan" not in data:
        print("error: input file must contain an 'active_plan' key", file=sys.stderr)
        return 1
    if "multipliers" not in data:
        print("error: input file must contain a 'multipliers' key", file=sys.stderr)
        return 1

    try:
        active_plan = PlanVersion.model_validate(data["active_plan"])
    except ValidationError as exc:
        print(f"error: invalid active_plan: {exc}", file=sys.stderr)
        return 1

    try:
        multipliers = UserDurationMultipliers.model_validate(data["multipliers"])
    except ValidationError as exc:
        print(f"error: invalid multipliers: {exc}", file=sys.stderr)
        return 1

    prop = propose_recalibrated_plan(
        active_plan,
        multipliers,
        id_generator=UuidIdGenerator(),
        clock=SystemClock(),
    )

    if prop is None:
        print("no duration change; nothing to recalibrate")
        return 0

    if args.emit_json:
        print(json.dumps(prop.diff.model_dump(mode="json"), indent=2))
    else:
        draft = prop.draft
        diff = prop.diff.summary
        print(f"draft plan_version:              {draft.plan_version}")
        print(f"state:                           {draft.state.value}")
        print(f"parent:                          {draft.parent_plan_version}")
        print(f"tasks_with_duration_changes:     {diff.tasks_with_duration_changes}")
        print(f"net_weekly_load_change_min:      {diff.net_weekly_load_change_min}")
        print(f"modules_affected:                {list(diff.modules_affected)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
