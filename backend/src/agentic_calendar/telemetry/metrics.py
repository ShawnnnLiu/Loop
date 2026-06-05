"""Deterministic telemetry metrics (Phase 4).

Pure functions over a list of :class:`TelemetryEvent`. Callers scope the list
first — to a user, and to a time window (the telemetry event carries no
scheduled date, so date-windowing uses the schedule the caller already holds;
these functions then compute rates over whatever set they are given, treating
one event as one scheduled task).

Targets these feed (axiom 09 "Cost and Metrics"):

* completion rate — users complete > 60% of scheduled tasks over 2 weeks;
* median duration estimate error — < 30%;
* schedule edit rate — generated schedules need < 25% manual edits.

Accountability-effectiveness metrics whose *inputs* live outside telemetry
(recovery-option selections, sponsor opt-ins, recorded in the notification log
and motivation profile) are exposed as count-based computations so the Phase 7
accountability layer can feed them without re-deriving the formula.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from statistics import median

from agentic_calendar.contracts.telemetry import TelemetryEvent


def _ratio(numerator: float, denominator: float) -> float:
    """Safe ratio: 0.0 when the denominator is 0 (no events ⇒ no signal)."""
    if denominator == 0:
        return 0.0
    return numerator / denominator


def _measured(events: Sequence[TelemetryEvent]) -> list[TelemetryEvent]:
    """Completed events whose ``actual_duration_min`` is a real measurement.

    Excludes ``duration_estimated`` events: their actual was defaulted to the
    scheduled duration, so their error is a fabricated 0 and would bias the
    metric toward "perfect".
    """
    return [
        e
        for e in events
        if e.completed
        and not e.duration_estimated
        and e.actual_duration_min is not None
    ]


def completion_rate(events: Sequence[TelemetryEvent]) -> float:
    """Fraction of events that completed, in ``[0, 1]`` (0.0 for an empty set)."""
    return _ratio(sum(1 for e in events if e.completed), len(events))


def median_duration_error(events: Sequence[TelemetryEvent]) -> float | None:
    """Median absolute relative duration error over measured completions.

    ``|actual - scheduled| / scheduled`` per event, then the median. Returns
    ``None`` when no measured completion exists (the metric is undefined, which
    is distinct from 0.0 "perfect").
    """
    measured = _measured(events)
    if not measured:
        return None
    errors = [
        abs(e.actual_duration_min - e.scheduled_duration_min) / e.scheduled_duration_min  # type: ignore[operator]
        for e in measured
    ]
    return median(errors)


def schedule_edit_rate(events: Sequence[TelemetryEvent]) -> float:
    """Fraction of events the user had to reschedule at least once."""
    return _ratio(sum(1 for e in events if e.user_reschedule_count > 0), len(events))


def completion_lift(
    baseline: Sequence[TelemetryEvent],
    current: Sequence[TelemetryEvent],
) -> float:
    """``completion_rate(current) - completion_rate(baseline)``.

    Positive means accountability/calibration improved completion. Signed.
    """
    return completion_rate(current) - completion_rate(baseline)


def acceptance_rate(*, offered: int, accepted: int) -> float:
    """Generic offered→accepted rate (e.g. recovery-plan acceptance).

    Inputs come from the notification log / recovery flow (Phase 7); the
    deterministic computation lives here so there is one definition.
    """
    if offered < 0 or accepted < 0:
        raise ValueError("offered and accepted must be non-negative")
    if accepted > offered:
        raise ValueError("accepted cannot exceed offered")
    return _ratio(accepted, offered)


def opt_in_rate(*, eligible: int, opted_in: int) -> float:
    """Generic eligible→opted-in rate (e.g. sponsor opt-in).

    Inputs come from the motivation profile (Phase 3); computation lives here.
    """
    if eligible < 0 or opted_in < 0:
        raise ValueError("eligible and opted_in must be non-negative")
    if opted_in > eligible:
        raise ValueError("opted_in cannot exceed eligible")
    return _ratio(opted_in, eligible)


@dataclass(frozen=True)
class MetricsReport:
    """Telemetry-native metrics for one scoped event set.

    ``median_duration_error`` is ``None`` when no measured completion exists.
    """

    sample_size: int
    completed_count: int
    completion_rate: float
    median_duration_error: float | None
    schedule_edit_rate: float

    @classmethod
    def from_events(cls, events: Sequence[TelemetryEvent]) -> MetricsReport:
        return cls(
            sample_size=len(events),
            completed_count=sum(1 for e in events if e.completed),
            completion_rate=completion_rate(events),
            median_duration_error=median_duration_error(events),
            schedule_edit_rate=schedule_edit_rate(events),
        )
