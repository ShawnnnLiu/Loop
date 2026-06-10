"""Completion dashboard: project accountability state and the policy decision.

Phase 7 deliverable — the internal operator view of ``completion_rate_7d``,
``behind_schedule_percent``, missed tasks, check-in status, and the
intervention the deterministic policy engine selects (with its full audit
log). This CLI is the composition root that wires the accountability region
to telemetry data from outside the region set.

Reads a JSON file shaped as::

    {
      "profile": { ...motivation_profile payload... },
      "plan_id": "plan_004",
      "timezone": "America/Los_Angeles",
      "events_7d": [ ...telemetry payloads... ],
      "events_14d": [ ...telemetry payloads... ],
      "checkin_events": [ ...checkin_event payloads... ],
      "scheduled_minutes_due": 360,
      "completed_minutes_due": 295
    }

Usage::

    uv run python -m agentic_calendar.tools.show_accountability state.json
    uv run python -m agentic_calendar.tools.show_accountability state.json \
        --at 2026-05-11T09:00:00-07:00 --json

``--at`` pins "now" for deterministic replay; ``--inactive`` evaluates with a
disabled contract (golden scenario 24).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import ValidationError

from agentic_calendar.accountability import (
    ProjectionInput,
    derive_accountability_contract,
    evaluate_accountability,
    evaluate_checkin,
)
from agentic_calendar.common.clock import Clock, FrozenClock, SystemClock
from agentic_calendar.common.ids import UuidIdGenerator
from agentic_calendar.contracts.checkin_event import CheckinEvent
from agentic_calendar.contracts.motivation_profile import MotivationProfile
from agentic_calendar.contracts.telemetry import TelemetryEvent


def _fail(message: str) -> int:
    print(f"error: {message}", file=sys.stderr)
    return 1


def _validate_events(raw: Any, label: str) -> list[TelemetryEvent]:
    if not isinstance(raw, list):
        raise ValueError(f"'{label}' must be a JSON array")
    return [TelemetryEvent.model_validate(item) for item in raw]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Project accountability state and the policy decision."
    )
    parser.add_argument("file", type=Path, help="Path to the dashboard input JSON.")
    parser.add_argument(
        "--at",
        type=str,
        default=None,
        help="ISO timestamp to pin 'now' for deterministic replay.",
    )
    parser.add_argument(
        "--inactive",
        action="store_true",
        help="Evaluate with the accountability contract disabled.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="emit_json",
        help="Emit state + decision as JSON instead of human-readable text.",
    )
    args = parser.parse_args(argv)

    try:
        data: Any = json.loads(args.file.read_text(encoding="utf-8"))
    except OSError as exc:
        return _fail(f"cannot read {args.file}: {exc}")
    except json.JSONDecodeError as exc:
        return _fail(f"invalid JSON in {args.file}: {exc}")
    if not isinstance(data, dict):
        return _fail(f"expected a JSON object, got {type(data).__name__}")

    clock: Clock
    if args.at is not None:
        try:
            pinned = datetime.fromisoformat(args.at)
        except ValueError as exc:
            return _fail(f"invalid --at timestamp: {exc}")
        if pinned.tzinfo is None:
            return _fail("--at must be timezone-aware (include an offset)")
        clock = FrozenClock(pinned)
    else:
        clock = SystemClock()

    try:
        tz = ZoneInfo(str(data.get("timezone", "")))
    except (ZoneInfoNotFoundError, TypeError, ValueError):
        return _fail("'timezone' must be a valid IANA timezone name")

    try:
        profile = MotivationProfile.model_validate(data.get("profile"))
        events_7d = _validate_events(data.get("events_7d", []), "events_7d")
        events_14d = _validate_events(data.get("events_14d", []), "events_14d")
        checkins = [CheckinEvent.model_validate(item) for item in data.get("checkin_events", [])]
    except (ValidationError, ValueError) as exc:
        return _fail(str(exc))

    plan_id = data.get("plan_id")
    scheduled_due = data.get("scheduled_minutes_due")
    completed_due = data.get("completed_minutes_due")
    if not isinstance(plan_id, str) or not plan_id:
        return _fail("'plan_id' must be a non-empty string")
    if not isinstance(scheduled_due, int) or not isinstance(completed_due, int):
        return _fail("'scheduled_minutes_due' and 'completed_minutes_due' must be integers")

    ids = UuidIdGenerator()
    contract = derive_accountability_contract(
        profile, id_generator=ids, clock=clock, active=not args.inactive
    )
    assessment = evaluate_checkin(contract, checkins, now=clock.now(), tz=tz)
    try:
        outcome = evaluate_accountability(
            ProjectionInput(
                user_id=profile.user_id,
                plan_id=plan_id,
                events_7d=events_7d,
                events_14d=events_14d,
                scheduled_minutes_due=scheduled_due,
                completed_minutes_due=completed_due,
            ),
            contract,
            assessment.status,
            clock=clock,
            id_generator=ids,
        )
    except ValueError as exc:
        return _fail(str(exc))

    state, decision = outcome.state, outcome.decision
    if args.emit_json:
        print(
            json.dumps(
                {
                    "checkin_status": assessment.status.value,
                    "state": state.model_dump(mode="json"),
                    "decision": decision.model_dump(mode="json"),
                },
                indent=2,
            )
        )
        return 0

    print(f"user / plan:             {state.user_id} / {state.plan_id}")
    print(f"completion_rate_7d:      {state.completion_rate_7d:.2f}")
    print(f"completion_rate_14d:     {state.completion_rate_14d:.2f}")
    print(f"missed_tasks_7d:         {state.missed_tasks_7d}")
    print(f"reschedule_count_7d:     {state.reschedule_count_7d}")
    print(f"behind_schedule_percent: {state.behind_schedule_percent}")
    print(f"weekly_checkin:          {assessment.status.value}")
    print(f"current_status:          {state.current_status.value}")
    print(f"sponsor_report_allowed:  {state.sponsor_report_allowed}")
    action = decision.action.value if decision.action else "none"
    reason = decision.reason_code.value if decision.reason_code else "none"
    print(f"intervention:            {action} ({reason})")
    sponsor_action = decision.sponsor_action.value if decision.sponsor_action else "none"
    print(f"sponsor_lane:            {sponsor_action}")
    if decision.evaluations:
        print("policy_audit:")
        for ev in decision.evaluations:
            flag = "MATCH" if ev.matched else "  -  "
            print(
                f"  [{flag}] {ev.policy_name}: observed "
                f"{ev.observed_value:g} vs threshold {ev.threshold_value:g}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
