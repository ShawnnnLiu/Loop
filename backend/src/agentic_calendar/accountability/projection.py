"""Deterministic accountability-state projection (Phase 7).

Spec: ``docs/specs/accountability-state.schema.md`` (axiom 21: the state "must
be recomputed from source events, never edited in place").

Following the ``DriftInput`` precedent, the caller scopes the telemetry
windows (7- and 14-day) and supplies the plan-to-date scheduled/completed
minutes; the projection is a pure function of those inputs. A missed task is a
telemetry event with ``completed: false`` — the same observable convention the
drift classifier uses.

``recommended_intervention`` is left ``None`` here; the policy engine fills it
when composing the final state (``engine.evaluate_accountability``). The
projection never decides anything — it only measures.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from agentic_calendar.common.clock import Clock
from agentic_calendar.contracts.accountability_contract import AccountabilityContract
from agentic_calendar.contracts.accountability_state import AccountabilityState
from agentic_calendar.contracts.common_types import AccountabilityStatus
from agentic_calendar.contracts.telemetry import TelemetryEvent

from .checkin import CheckinStatus

#: ``disengaged`` floor on the 14-day completion rate — heuristic prior.
DISENGAGED_COMPLETION_FLOOR: float = 0.2


@dataclass(frozen=True)
class ProjectionInput:
    """Caller-scoped observable inputs for one user and plan.

    ``events_7d`` must be a subset of ``events_14d`` (both windows end now);
    the projection validates that invariant cheaply by length. Minutes are
    plan-to-date: how much was scheduled to be done by now vs how much was.
    """

    user_id: str
    plan_id: str
    events_7d: Sequence[TelemetryEvent]
    events_14d: Sequence[TelemetryEvent]
    scheduled_minutes_due: int
    completed_minutes_due: int


def _completion_rate(events: Sequence[TelemetryEvent]) -> float:
    """Completed ÷ total, rounded to 2 dp; 1.0 on an empty window.

    An empty window is *absence of evidence* of being behind, not evidence of
    disengagement — disengagement must come from a populated window.
    """
    if not events:
        return 1.0
    return round(sum(1 for e in events if e.completed) / len(events), 2)


def behind_schedule_percent(*, scheduled_minutes_due: int, completed_minutes_due: int) -> int:
    """Spec "Behind-Schedule Formula": round-half-up, clamped to [0, 100]."""
    if scheduled_minutes_due <= 0:
        return 0
    shortfall = max(0, scheduled_minutes_due - completed_minutes_due)
    return min(100, math.floor(100 * shortfall / scheduled_minutes_due + 0.5))


def _status(
    *,
    completion_rate_14d: float,
    behind_pct: int,
    missed_tasks_7d: int,
    threshold_pct: int,
) -> AccountabilityStatus:
    """Spec "Status Thresholds": evaluated top-down, first match wins."""
    if completion_rate_14d < DISENGAGED_COMPLETION_FLOOR:
        return AccountabilityStatus.DISENGAGED
    if behind_pct >= 2 * threshold_pct:
        return AccountabilityStatus.FAR_BEHIND
    if behind_pct >= threshold_pct:
        return AccountabilityStatus.BEHIND
    if behind_pct >= math.ceil(threshold_pct / 2) or missed_tasks_7d >= 1:
        return AccountabilityStatus.SLIGHTLY_BEHIND
    return AccountabilityStatus.ON_TRACK


def project_accountability_state(
    inp: ProjectionInput,
    contract: AccountabilityContract,
    checkin_status: CheckinStatus,
    *,
    clock: Clock,
) -> AccountabilityState:
    """Project the deterministic accountability state (no decision made)."""
    if len(inp.events_7d) > len(inp.events_14d):
        raise ValueError("events_7d cannot exceed events_14d (nested windows)")

    behind_pct = behind_schedule_percent(
        scheduled_minutes_due=inp.scheduled_minutes_due,
        completed_minutes_due=inp.completed_minutes_due,
    )
    rate_14d = _completion_rate(inp.events_14d)
    missed_7d = sum(1 for e in inp.events_7d if not e.completed)

    return AccountabilityState(
        user_id=inp.user_id,
        plan_id=inp.plan_id,
        completion_rate_7d=_completion_rate(inp.events_7d),
        completion_rate_14d=rate_14d,
        missed_tasks_7d=missed_7d,
        reschedule_count_7d=sum(e.user_reschedule_count for e in inp.events_7d),
        behind_schedule_percent=behind_pct,
        weekly_checkin_completed=checkin_status
        in (CheckinStatus.COMPLETED, CheckinStatus.NOT_REQUIRED),
        current_status=_status(
            completion_rate_14d=rate_14d,
            behind_pct=behind_pct,
            missed_tasks_7d=missed_7d,
            threshold_pct=contract.effective_behind_schedule_intervention_threshold_pct,
        ),
        recommended_intervention=None,
        sponsor_report_allowed=contract.sponsor_reporting_allowed,
        sponsor_report_level=contract.sponsor_visibility_level,
        computed_at=clock.now(),
    )
