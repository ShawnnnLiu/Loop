"""Full preview → approve → write flow against the in-memory calendar adapter.

This is the operational entry point for testing the Calendar Write Manager
end-to-end without contacting any external service. Failure modes can be
injected via ``--fail-task-id`` so the partial-failure path is reachable.

Usage::

    uv run python -m agentic_calendar.tools.write_calendar --scenario success
    uv run python -m agentic_calendar.tools.write_calendar --scenario success --fail-task-id dp_001
    uv run python -m agentic_calendar.tools.write_calendar --scenario success --dry-run
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
    """Recursive default for json.dumps that handles dataclasses + pydantic + datetime."""
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return str(value)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run the full approve_and_write flow against an in-memory adapter "
            "for one scheduler scenario. No external API calls."
        )
    )
    parser.add_argument("--scenario", required=False)
    parser.add_argument(
        "--target-calendar-id", default=DEFAULT_TARGET_CALENDAR_ID
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Compute and print the preview only; never call the adapter. "
            "Equivalent to invoking preview_calendar_write."
        ),
    )
    parser.add_argument(
        "--fail-task-id",
        action="append",
        default=[],
        help=(
            "Inject FailureModes.fail_create_for_task_ids; may be passed "
            "more than once. The matching task(s) will raise on create."
        ),
    )
    parser.add_argument(
        "--drop-task-id",
        action="append",
        default=[],
        help=(
            "Inject FailureModes.drop_silently_for_task_ids; the matching "
            "task(s) appear to write but are absent from verification."
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
    if args.fail_task_id or args.drop_task_id:
        failure_modes = FailureModes(
            fail_create_for_task_ids=frozenset(args.fail_task_id),
            drop_silently_for_task_ids=frozenset(args.drop_task_id),
        )

    env = make_environment(failure_modes=failure_modes)
    try:
        draft = build_draft_for_scenario(args.scenario, env)
    except (KeyError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.dry_run:
        preview = env.manager.preview(
            draft=draft, target_calendar_id=args.target_calendar_id
        )
        print(
            json.dumps(
                {"mode": "dry_run", "preview": _serialize(preview)},
                indent=2,
                sort_keys=True,
                default=_serialize,
            )
        )
        return 0

    approval = create_approval(draft, env)
    # No task_titles: scenario drafts over the in-memory adapter keep the
    # generic fallback summary on purpose.
    result = env.manager.approve_and_write(
        approval_event_id=approval.approval_event_id,
        draft=draft,
        target_calendar_id=args.target_calendar_id,
    )
    final_mappings = env.mapping_store.list_for_run(result.run_id or "")
    payload = {
        "mode": "write",
        "approval_event_id": approval.approval_event_id,
        "result": _serialize(result),
        "final_mappings": [_serialize(m) for m in final_mappings],
    }
    print(json.dumps(payload, indent=2, sort_keys=True, default=_serialize))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
