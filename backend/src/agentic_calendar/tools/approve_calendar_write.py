"""Produce a deterministic ``ApprovalEvent`` for a scenario draft.

This CLI exercises the seam between the (future) approval UI and the
Calendar Write Manager: given a scheduler scenario, it builds a draft,
computes the canonical payload hash, and prints the resulting
:class:`ApprovalEvent` as JSON. The approval is also persisted in an
in-memory store, but since the store is in-process, the value of this CLI is
the byte-stable JSON output rather than persistence.

Usage::

    uv run python -m agentic_calendar.tools.approve_calendar_write --scenario success
"""

from __future__ import annotations

import argparse
import sys

from ._calendar_cli_common import (
    build_draft_for_scenario,
    create_approval,
    list_scenario_names,
    make_environment,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build a deterministic ApprovalEvent for a scheduler scenario "
            "and print it as JSON."
        )
    )
    parser.add_argument(
        "--scenario",
        required=False,
        help="Scenario name to approve (omit + use --list to see options).",
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
        return 2

    env = make_environment()
    try:
        draft = build_draft_for_scenario(args.scenario, env)
    except (KeyError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    approval = create_approval(draft, env)
    print(approval.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
