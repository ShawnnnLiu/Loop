"""Verify every mapping for a scenario's write against the in-memory adapter.

Because Phase 2 stores are in-process, this CLI runs the full
preview→approve→write flow first to populate state, then exercises
``CalendarWriteManager.verify``. Failure modes can be injected to make
verification fail.

Usage::

    uv run python -m agentic_calendar.tools.verify_calendar --scenario success
    uv run python -m agentic_calendar.tools.verify_calendar --scenario success --drop-task-id dp_001
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from typing import Any

from agentic_calendar.calendar_writer import FailureModes

from ._calendar_cli_common import (
    DEFAULT_TARGET_CALENDAR_ID,
    build_draft_for_scenario,
    create_approval,
    list_scenario_names,
    make_environment,
)


def _serialize(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return str(value)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run a full write then verify it. In-memory only; no external "
            "API calls."
        )
    )
    parser.add_argument("--scenario", required=False)
    parser.add_argument(
        "--target-calendar-id", default=DEFAULT_TARGET_CALENDAR_ID
    )
    parser.add_argument(
        "--drop-task-id",
        action="append",
        default=[],
        help=(
            "Inject FailureModes.drop_silently_for_task_ids; the matching "
            "task(s) will fail verification."
        ),
    )
    parser.add_argument(
        "--corrupt-task-id",
        action="append",
        default=[],
        help=(
            "Inject FailureModes.corrupt_metadata_for_task_ids; verification "
            "will see mismatched metadata for the matching task(s)."
        ),
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

    failure_modes: FailureModes | None = None
    if args.drop_task_id or args.corrupt_task_id:
        failure_modes = FailureModes(
            drop_silently_for_task_ids=frozenset(args.drop_task_id),
            corrupt_metadata_for_task_ids=frozenset(args.corrupt_task_id),
        )

    env = make_environment(failure_modes=failure_modes)
    try:
        draft = build_draft_for_scenario(args.scenario, env)
    except (KeyError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    approval = create_approval(draft, env)
    # No task_titles: scenario drafts over the in-memory adapter keep the
    # generic fallback summary on purpose.
    write_result = env.manager.approve_and_write(
        approval_event_id=approval.approval_event_id,
        draft=draft,
        target_calendar_id=args.target_calendar_id,
    )
    if write_result.run_id is None:
        print(
            json.dumps(
                {
                    "error": "write produced no run_id",
                    "result": _serialize(write_result),
                },
                indent=2,
                default=_serialize,
            )
        )
        return 1

    verification = env.manager.verify(
        run_id=write_result.run_id, target_calendar_id=args.target_calendar_id
    )
    payload = {
        "run_id": write_result.run_id,
        "write_result": _serialize(write_result),
        "verification": _serialize(verification),
    }
    print(json.dumps(payload, indent=2, sort_keys=True, default=_serialize))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
