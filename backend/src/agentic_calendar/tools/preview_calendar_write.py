"""Preview what a calendar write would do for a scenario, without side effects.

The preview path (axiom 06 lines 124-130 wraps this in a broader UX; the
deterministic core is just ``CalendarWriteManager.preview``) computes the
planned events + canonical payload hash without touching the adapter. Use
this CLI to see what the user would be asked to approve.

Usage::

    uv run python -m agentic_calendar.tools.preview_calendar_write --scenario success
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict

from agentic_calendar.calendar_writer import PreviewResult

from ._calendar_cli_common import (
    DEFAULT_TARGET_CALENDAR_ID,
    build_draft_for_scenario,
    list_scenario_names,
    make_environment,
)


def _render(result: PreviewResult) -> str:
    return json.dumps(asdict(result), indent=2, sort_keys=True, default=str)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Compute the preview of a calendar write for a scheduler scenario. "
            "No external API calls are made."
        )
    )
    parser.add_argument(
        "--scenario",
        required=False,
        help="Scenario name to preview (omit + use --list to see options).",
    )
    parser.add_argument(
        "--target-calendar-id",
        default=DEFAULT_TARGET_CALENDAR_ID,
        help=f"External calendar id (default: {DEFAULT_TARGET_CALENDAR_ID}).",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available scenarios and exit.",
    )
    args = parser.parse_args(argv)

    if args.list:
        for name in list_scenario_names():
            print(name)
        return 0
    if not args.scenario:
        parser.error("--scenario is required (or pass --list)")
        return 2  # unreachable; parser.error exits

    env = make_environment()
    try:
        draft = build_draft_for_scenario(args.scenario, env)
    except (KeyError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    result = env.manager.preview(
        draft=draft, target_calendar_id=args.target_calendar_id
    )
    print(_render(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
