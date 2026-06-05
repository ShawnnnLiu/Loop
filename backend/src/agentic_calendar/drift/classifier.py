"""Deterministic drift classifier (Phase 4, axiom 07).

``DriftClassifier.classify`` runs one rule per :class:`DriftType` over a
:class:`DriftInput` bundle and returns the drift events that fired, in a stable
canonical order. No randomness, no LLM: the same input always yields the same
events, ids aside (ids/timestamps come from the injected
``IdGenerator``/``Clock``, so tests pin them with the deterministic variants).

Data availability is honest. The telemetry-native rules (duration drift,
low-engagement, topic-avoidance, dependency-blocked, and external-conflict via
reschedule correlation) run from telemetry + the plan. Two rules need inputs
the MVP does not yet wire — ``capacity_mismatch`` needs per-cycle scheduled
minutes and ``calendar_fragmentation`` needs free/busy blocks — so they fire
only when the caller supplies those optional signals (they will activate
unchanged once the calendar adapter lands). A rule whose required input is
absent is *skipped*, never faked.

Confidence is a deterministic function of how far past threshold the signal ran
and how much evidence backed it — never an LLM guess.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from statistics import median

from agentic_calendar.common.clock import Clock
from agentic_calendar.common.ids import IdGenerator
from agentic_calendar.contracts.common_types import FocusLevel, TaskCategory
from agentic_calendar.contracts.drift_event import (
    DRIFT_TYPE_TO_REASON_CODE,
    DriftEvent,
    DriftEvidence,
    DriftType,
)
from agentic_calendar.contracts.task_plan import TaskPlan
from agentic_calendar.contracts.telemetry import TelemetryEvent
from agentic_calendar.prerequisites.compute import compute_runtime_view

from .policy import DRIFT_TYPE_TO_ACTION
from .thresholds import DEFAULT_DRIFT_THRESHOLDS, DriftThresholds

_DRIFT_ORDER: dict[DriftType, int] = {dt: i for i, dt in enumerate(DriftType)}


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _confidence(*, magnitude: float, sample_size: int, sample_target: int) -> float:
    """Deterministic confidence in ``[0.5, 1.0]`` for a fired rule.

    ``0.5`` floor because the rule already crossed its threshold; the remaining
    range rewards a larger threshold exceedance (``magnitude``, rule-normalized
    to ``[0, 1]``) and a larger evidence base (``sample_size`` toward
    ``sample_target``). Rounded to 2 dp for stable JSON.
    """
    sample_factor = min(sample_size / sample_target, 1.0) if sample_target > 0 else 1.0
    raw = 0.5 + 0.3 * _clamp01(magnitude) + 0.2 * sample_factor
    return round(_clamp01(raw), 2)


@dataclass(frozen=True)
class WeeklyCapacity:
    """One cycle's scheduled vs completed study minutes (caller-derived)."""

    scheduled_min: int
    completed_min: int


@dataclass(frozen=True)
class FragmentationSignal:
    """Free/busy facts for the upcoming window (caller-derived from calendar)."""

    total_free_min: int
    largest_free_block_min: int


@dataclass(frozen=True)
class DriftInput:
    """Everything the classifier needs, bundled.

    ``events`` must be scoped to one user by the caller. ``weekly_cycles`` and
    ``fragmentation`` are optional; the rules that need them are skipped when
    absent. ``external_conflict_task_ids`` marks tasks the caller knows hit an
    external calendar conflict (telemetry reschedule counts are also used, so
    this rule can fire without it).
    """

    plan: TaskPlan
    events: Sequence[TelemetryEvent]
    weekly_cycles: Sequence[WeeklyCapacity] = ()
    fragmentation: FragmentationSignal | None = None
    external_conflict_task_ids: frozenset[str] = field(default_factory=frozenset)


class DriftClassifier:
    """Rule-based, deterministic plan-drift classifier."""

    def __init__(
        self,
        *,
        clock: Clock,
        id_generator: IdGenerator,
        thresholds: DriftThresholds = DEFAULT_DRIFT_THRESHOLDS,
    ) -> None:
        self._clock = clock
        self._ids = id_generator
        self.t = thresholds

    def classify(self, drift_input: DriftInput) -> list[DriftEvent]:
        """Return every drift event that fired, in stable canonical order."""
        task_category = {t.task_id: t.category for t in drift_input.plan.tasks}

        events: list[DriftEvent] = []
        events += self._duration_rules(drift_input, task_category)
        events += self._capacity_rule(drift_input)
        events += self._topic_avoidance_rule(drift_input, task_category)
        events += self._external_conflict_rule(drift_input)
        events += self._low_engagement_rule(drift_input, task_category)
        events += self._dependency_blocked_rule(drift_input)
        events += self._fragmentation_rule(drift_input)

        events.sort(
            key=lambda e: (
                _DRIFT_ORDER[e.drift_type],
                tuple(c.value for c in e.evidence.affected_categories),
                e.evidence.trigger_metric,
            )
        )
        return events

    # -- rule implementations -------------------------------------------------

    def _duration_rules(
        self, di: DriftInput, task_category: Mapping[str, TaskCategory]
    ) -> list[DriftEvent]:
        ratios_by_cat: dict[TaskCategory, list[float]] = {}
        for e in di.events:
            if not e.completed or e.duration_estimated or e.actual_duration_min is None:
                continue
            if e.scheduled_duration_min <= 0:
                continue
            cat = task_category.get(e.task_id)
            if cat is None:
                continue
            ratios_by_cat.setdefault(cat, []).append(
                e.actual_duration_min / e.scheduled_duration_min
            )

        out: list[DriftEvent] = []
        for cat in sorted(ratios_by_cat, key=lambda c: c.value):
            ratios = ratios_by_cat[cat]
            if len(ratios) < self.t.duration_min_sample:
                continue
            med = median(ratios)
            if med > self.t.duration_underestimate_ratio:
                threshold = self.t.duration_underestimate_ratio
                magnitude = (med - threshold) / threshold
                out.append(
                    self._event(
                        DriftType.DURATION_UNDERESTIMATE,
                        evidence=DriftEvidence(
                            trigger_metric="median_actual_vs_predicted_ratio",
                            trigger_value=round(med, 4),
                            threshold=threshold,
                            sample_size=len(ratios),
                            affected_categories=[cat],
                        ),
                        magnitude=magnitude,
                        sample_size=len(ratios),
                        sample_target=2 * self.t.duration_min_sample,
                        plan_version=di.plan.plan_version,
                    )
                )
            elif med < self.t.duration_overestimate_ratio:
                threshold = self.t.duration_overestimate_ratio
                magnitude = (threshold - med) / threshold
                out.append(
                    self._event(
                        DriftType.DURATION_OVERESTIMATE,
                        evidence=DriftEvidence(
                            trigger_metric="median_actual_vs_predicted_ratio",
                            trigger_value=round(med, 4),
                            threshold=threshold,
                            sample_size=len(ratios),
                            affected_categories=[cat],
                        ),
                        magnitude=magnitude,
                        sample_size=len(ratios),
                        sample_target=2 * self.t.duration_min_sample,
                        plan_version=di.plan.plan_version,
                    )
                )
        return out

    def _capacity_rule(self, di: DriftInput) -> list[DriftEvent]:
        cycles = list(di.weekly_cycles)
        if len(cycles) < self.t.capacity_min_cycles:
            return []
        recent = cycles[-self.t.capacity_min_cycles :]
        ratios: list[float] = []
        for c in recent:
            if c.scheduled_min <= 0:
                return []  # cannot assess a cycle with no scheduled minutes
            ratios.append(c.completed_min / c.scheduled_min)
        best_recent = max(ratios)  # all recent cycles below floor ⟺ best < floor
        if best_recent >= self.t.capacity_completion_floor:
            return []
        magnitude = (self.t.capacity_completion_floor - best_recent) / (
            self.t.capacity_completion_floor
        )
        return [
            self._event(
                DriftType.CAPACITY_MISMATCH,
                evidence=DriftEvidence(
                    trigger_metric="weekly_completion_ratio",
                    trigger_value=round(best_recent, 4),
                    threshold=self.t.capacity_completion_floor,
                    sample_size=len(recent),
                ),
                magnitude=magnitude,
                sample_size=len(recent),
                sample_target=self.t.capacity_min_cycles,
                plan_version=di.plan.plan_version,
            )
        ]

    def _topic_avoidance_rule(
        self, di: DriftInput, task_category: Mapping[str, TaskCategory]
    ) -> list[DriftEvent]:
        by_cat: dict[TaskCategory, list[TelemetryEvent]] = {}
        for e in di.events:
            cat = task_category.get(e.task_id)
            if cat is None:
                continue
            by_cat.setdefault(cat, []).append(e)

        completion = {
            cat: sum(1 for e in evs if e.completed) / len(evs)
            for cat, evs in by_cat.items()
        }

        out: list[DriftEvent] = []
        for cat in sorted(by_cat, key=lambda c: c.value):
            evs = by_cat[cat]
            avoided = sum(
                1 for e in evs if (not e.completed) or e.user_reschedule_count >= 1
            )
            if avoided < self.t.topic_avoidance_min_events:
                continue
            # "while other modules complete": some OTHER category is progressing,
            # which separates avoidance of one topic from broad disengagement.
            others_ok = any(c != cat and completion[c] >= 0.5 for c in by_cat)
            if not others_ok:
                continue
            magnitude = avoided / (self.t.topic_avoidance_min_events * 2)
            out.append(
                self._event(
                    DriftType.TOPIC_AVOIDANCE,
                    evidence=DriftEvidence(
                        trigger_metric="missed_or_rescheduled_count",
                        trigger_value=float(avoided),
                        threshold=float(self.t.topic_avoidance_min_events),
                        sample_size=len(evs),
                        affected_categories=[cat],
                    ),
                    magnitude=magnitude,
                    sample_size=len(evs),
                    sample_target=self.t.topic_avoidance_min_events * 2,
                    plan_version=di.plan.plan_version,
                )
            )
        return out

    def _external_conflict_rule(self, di: DriftInput) -> list[DriftEvent]:
        missed = [e for e in di.events if not e.completed]
        if len(missed) < self.t.external_conflict_min_misses:
            return []
        associated = [
            e
            for e in missed
            if e.task_id in di.external_conflict_task_ids
            or e.user_reschedule_count >= self.t.external_conflict_reschedule_threshold
        ]
        ratio = len(associated) / len(missed)
        if ratio < self.t.external_conflict_correlation:
            return []
        floor = self.t.external_conflict_correlation
        magnitude = (ratio - floor) / (1 - floor) if floor < 1 else 1.0
        return [
            self._event(
                DriftType.EXTERNAL_CONFLICT,
                evidence=DriftEvidence(
                    trigger_metric="conflict_associated_miss_ratio",
                    trigger_value=round(ratio, 4),
                    threshold=floor,
                    sample_size=len(missed),
                ),
                magnitude=magnitude,
                sample_size=len(missed),
                sample_target=2 * self.t.external_conflict_min_misses,
                plan_version=di.plan.plan_version,
            )
        ]

    def _low_engagement_rule(
        self, di: DriftInput, task_category: Mapping[str, TaskCategory]
    ) -> list[DriftEvent]:
        events = list(di.events)
        if len(events) < self.t.low_engagement_min_sample:
            return []
        incomplete = [e for e in events if not e.completed]
        skip_rate = len(incomplete) / len(events)
        miss_cats = {task_category.get(e.task_id) for e in incomplete}
        miss_cats.discard(None)
        if (
            skip_rate < self.t.low_engagement_skip_rate
            or len(miss_cats) < self.t.low_engagement_min_categories
        ):
            return []
        floor = self.t.low_engagement_skip_rate
        magnitude = (skip_rate - floor) / (1 - floor) if floor < 1 else 1.0
        return [
            self._event(
                DriftType.LOW_ENGAGEMENT,
                evidence=DriftEvidence(
                    trigger_metric="incomplete_rate",
                    trigger_value=round(skip_rate, 4),
                    threshold=floor,
                    sample_size=len(events),
                ),
                magnitude=magnitude,
                sample_size=len(events),
                sample_target=2 * self.t.low_engagement_min_sample,
                plan_version=di.plan.plan_version,
            )
        ]

    def _dependency_blocked_rule(self, di: DriftInput) -> list[DriftEvent]:
        completed_ids = {e.task_id for e in di.events if e.completed}
        missed_ids = {e.task_id for e in di.events if not e.completed}
        runtime = compute_runtime_view(di.plan, completed_task_ids=completed_ids)
        blocked = [
            rt.task_id
            for rt in runtime
            if rt.task_id not in completed_ids
            and any(dep in missed_ids for dep in rt.blocked_by)
        ]
        count = len(blocked)
        if count < self.t.dependency_blocked_min:
            return []
        magnitude = count / 3
        return [
            self._event(
                DriftType.DEPENDENCY_BLOCKED,
                evidence=DriftEvidence(
                    trigger_metric="downstream_tasks_blocked",
                    trigger_value=float(count),
                    threshold=float(self.t.dependency_blocked_min),
                    sample_size=count,
                ),
                magnitude=magnitude,
                sample_size=count,
                sample_target=3,
                plan_version=di.plan.plan_version,
            )
        ]

    def _fragmentation_rule(self, di: DriftInput) -> list[DriftEvent]:
        frag = di.fragmentation
        if frag is None:
            return []
        deep_durations = [
            t.estimated_duration_min
            for t in di.plan.tasks
            if t.required_focus_level is FocusLevel.DEEP
        ]
        if not deep_durations:
            return []
        required = max(deep_durations)
        unplaceable = sum(
            1
            for t in di.plan.tasks
            if t.required_focus_level is FocusLevel.DEEP
            and t.estimated_duration_min > frag.largest_free_block_min
        )
        fits_in_total = required <= frag.total_free_min
        too_fragmented = frag.largest_free_block_min < required
        if not (fits_in_total and too_fragmented and unplaceable >= 1):
            return []
        magnitude = (required - frag.largest_free_block_min) / required
        return [
            self._event(
                DriftType.CALENDAR_FRAGMENTATION,
                evidence=DriftEvidence(
                    trigger_metric="largest_free_block_min",
                    trigger_value=float(frag.largest_free_block_min),
                    threshold=float(required),
                    sample_size=unplaceable,
                ),
                magnitude=magnitude,
                sample_size=unplaceable,
                sample_target=3,
                plan_version=di.plan.plan_version,
            )
        ]

    # -- event construction ---------------------------------------------------

    def _event(
        self,
        drift_type: DriftType,
        *,
        evidence: DriftEvidence,
        magnitude: float,
        sample_size: int,
        sample_target: int,
        plan_version: str,
    ) -> DriftEvent:
        return DriftEvent(
            drift_event_id=self._ids.new_id("drift"),
            plan_version=plan_version,
            drift_detected=True,
            drift_type=drift_type,
            reason_code=DRIFT_TYPE_TO_REASON_CODE[drift_type],
            confidence=_confidence(
                magnitude=magnitude,
                sample_size=sample_size,
                sample_target=sample_target,
            ),
            evidence=evidence,
            recommended_policy_action=DRIFT_TYPE_TO_ACTION[drift_type],
            detected_at=self._clock.now(),
        )
