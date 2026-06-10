"""Deterministic drift-classifier tests (Phase 4, axiom 07).

One trigger test per drift type, plus boundary tests at each threshold value
(strictly-greater vs equal, sample-size floors, correlation floors). Scenarios
are crafted to isolate the target drift type; where two rules could co-fire the
test asserts membership rather than exact equality.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from agentic_calendar.common.clock import FrozenClock
from agentic_calendar.common.ids import DeterministicIdGenerator
from agentic_calendar.contracts.common_types import FocusLevel, TaskCategory
from agentic_calendar.contracts.drift_event import (
    DRIFT_TYPE_TO_REASON_CODE,
    DriftEvent,
    DriftType,
)
from agentic_calendar.contracts.task_plan import Task, TaskPlan
from agentic_calendar.contracts.telemetry import DataQuality, TelemetryEvent
from agentic_calendar.drift import (
    DriftClassifier,
    DriftInput,
    FragmentationSignal,
    WeeklyCapacity,
)

TS = datetime(2026, 5, 12, tzinfo=UTC)
C = TaskCategory


def _task(
    tid: str,
    cat: TaskCategory = C.PRACTICE,
    *,
    dur: int = 90,
    focus: FocusLevel = FocusLevel.MEDIUM,
    deps: Sequence[str] = (),
) -> Task:
    return Task(
        task_id=tid,
        module_id=f"m_{tid}",
        title=tid,
        estimated_duration_min=dur,
        cognitive_load=3,
        category=cat,
        required_focus_level=focus,
        dependencies=list(deps),
    )


def _ev(
    tid: str,
    *,
    sched: int = 90,
    actual: int = 135,
    completed: bool = True,
    reschedule: int = 0,
    dq: DataQuality = DataQuality.COMPLETE,
    estimated: bool = False,
) -> TelemetryEvent:
    return TelemetryEvent(
        telemetry_event_id=f"tel_{tid}",
        task_id=tid,
        scheduled_duration_min=sched,
        actual_duration_min=actual if completed else None,
        completed=completed,
        completion_timestamp=TS if completed else None,
        user_reschedule_count=reschedule,
        data_quality=dq,
        duration_estimated=estimated,
    )


def _classify(
    tasks: Sequence[Task], events: Sequence[TelemetryEvent], **kw: object
) -> list[DriftEvent]:
    plan = TaskPlan(plan_version="pv1", tasks=list(tasks))
    clf = DriftClassifier(
        clock=FrozenClock(TS), id_generator=DeterministicIdGenerator()
    )
    return clf.classify(DriftInput(plan=plan, events=list(events), **kw))  # type: ignore[arg-type]


def _types(events: Sequence[DriftEvent]) -> set[DriftType]:
    return {e.drift_type for e in events}


def _of(events: Sequence[DriftEvent], dt: DriftType) -> DriftEvent:
    matches = [e for e in events if e.drift_type is dt]
    assert matches, f"expected {dt} in {[e.drift_type for e in events]}"
    return matches[0]


# --------------------------------------------------------------------------- #
# duration_underestimate / duration_overestimate
# --------------------------------------------------------------------------- #


def test_duration_underestimate_triggers() -> None:
    tasks = [_task(f"p{i}", C.PRACTICE) for i in range(5)]
    events = [_ev(f"p{i}", sched=90, actual=135) for i in range(5)]  # ratio 1.5
    res = _classify(tasks, events)
    assert _types(res) == {DriftType.DURATION_UNDERESTIMATE}
    e = _of(res, DriftType.DURATION_UNDERESTIMATE)
    assert e.reason_code is DRIFT_TYPE_TO_REASON_CODE[DriftType.DURATION_UNDERESTIMATE]
    assert e.evidence.affected_categories == [C.PRACTICE]
    assert e.evidence.trigger_value == 1.5
    assert 0.5 <= e.confidence <= 1.0


def test_duration_underestimate_ratio_boundary_is_strict() -> None:
    # median exactly 1.30 does NOT fire (rule is strictly greater)
    at = _classify(
        [_task(f"p{i}") for i in range(5)],
        [_ev(f"p{i}", sched=100, actual=130) for i in range(5)],  # ratio 1.30
    )
    assert DriftType.DURATION_UNDERESTIMATE not in _types(at)
    # just above does fire
    above = _classify(
        [_task(f"p{i}") for i in range(5)],
        [_ev(f"p{i}", sched=100, actual=131) for i in range(5)],  # ratio 1.31
    )
    assert DriftType.DURATION_UNDERESTIMATE in _types(above)


def test_duration_sample_size_boundary() -> None:
    # 4 measured completions < min sample (5) -> no fire
    four = _classify(
        [_task(f"p{i}") for i in range(4)],
        [_ev(f"p{i}", sched=90, actual=135) for i in range(4)],
    )
    assert DriftType.DURATION_UNDERESTIMATE not in _types(four)


def test_duration_overestimate_triggers_and_boundary() -> None:
    over = _classify(
        [_task(f"p{i}") for i in range(5)],
        [_ev(f"p{i}", sched=100, actual=60) for i in range(5)],  # ratio 0.60
    )
    assert DriftType.DURATION_OVERESTIMATE in _types(over)
    # exactly 0.70 does not fire (strictly less)
    at = _classify(
        [_task(f"p{i}") for i in range(5)],
        [_ev(f"p{i}", sched=100, actual=70) for i in range(5)],  # ratio 0.70
    )
    assert DriftType.DURATION_OVERESTIMATE not in _types(at)


def test_estimated_durations_do_not_drive_duration_drift() -> None:
    # estimated actuals are fake (ratio 1.0); they must be ignored
    res = _classify(
        [_task(f"p{i}") for i in range(5)],
        [
            _ev(f"p{i}", sched=90, actual=90, estimated=True, dq=DataQuality.PARTIAL_ESTIMATED)
            for i in range(5)
        ],
    )
    assert DriftType.DURATION_UNDERESTIMATE not in _types(res)
    assert DriftType.DURATION_OVERESTIMATE not in _types(res)


# --------------------------------------------------------------------------- #
# capacity_mismatch
# --------------------------------------------------------------------------- #


def test_capacity_mismatch_triggers_on_two_low_cycles() -> None:
    res = _classify(
        [_task("t1")],
        [],
        weekly_cycles=[WeeklyCapacity(600, 300), WeeklyCapacity(600, 200)],
    )
    e = _of(res, DriftType.CAPACITY_MISMATCH)
    assert e.evidence.trigger_metric == "weekly_completion_ratio"
    assert e.evidence.sample_size == 2
    # trigger_value is the best of the recent cycles: max(0.5, 0.333) = 0.5
    assert e.evidence.trigger_value == 0.5


def test_capacity_floor_boundary_is_strict() -> None:
    # both cycles exactly at 60% -> not below floor -> no fire
    at = _classify(
        [_task("t1")],
        [],
        weekly_cycles=[WeeklyCapacity(600, 360), WeeklyCapacity(600, 360)],
    )
    assert DriftType.CAPACITY_MISMATCH not in _types(at)
    # just below the floor (59% both cycles) -> fires
    below = _classify(
        [_task("t1")],
        [],
        weekly_cycles=[WeeklyCapacity(600, 354), WeeklyCapacity(600, 354)],
    )
    assert DriftType.CAPACITY_MISMATCH in _types(below)


def test_capacity_needs_two_cycles_and_uses_most_recent_two() -> None:
    one = _classify([_task("t1")], [], weekly_cycles=[WeeklyCapacity(600, 100)])
    assert DriftType.CAPACITY_MISMATCH not in _types(one)
    # recent two are healthy even though an older cycle was low -> no fire
    recovered = _classify(
        [_task("t1")],
        [],
        weekly_cycles=[
            WeeklyCapacity(600, 100),
            WeeklyCapacity(600, 500),
            WeeklyCapacity(600, 540),
        ],
    )
    assert DriftType.CAPACITY_MISMATCH not in _types(recovered)


def test_capacity_zero_scheduled_cycle_does_not_suppress_collapse() -> None:
    # A planned break week (scheduled_min=0) between two collapse cycles must
    # not veto the rule: the assessable cycles still show total collapse.
    res = _classify(
        [_task("t1")],
        [],
        weekly_cycles=[
            WeeklyCapacity(600, 0),
            WeeklyCapacity(0, 0),  # break week — not assessable
            WeeklyCapacity(600, 0),
        ],
    )
    e = _of(res, DriftType.CAPACITY_MISMATCH)
    assert e.evidence.sample_size == 2
    assert e.evidence.trigger_value == 0.0


def test_capacity_requires_min_assessable_cycles() -> None:
    # One assessable collapse cycle + one break week: only a single
    # assessable cycle exists, below capacity_min_cycles -> no fire.
    res = _classify(
        [_task("t1")],
        [],
        weekly_cycles=[WeeklyCapacity(0, 0), WeeklyCapacity(600, 0)],
    )
    assert DriftType.CAPACITY_MISMATCH not in _types(res)


# --------------------------------------------------------------------------- #
# topic_avoidance
# --------------------------------------------------------------------------- #


def test_topic_avoidance_triggers_when_one_category_lags() -> None:
    tasks = [_task(f"p{i}", C.PRACTICE) for i in range(3)] + [
        _task(f"c{i}", C.CONCEPT_REVIEW) for i in range(2)
    ]
    events = [_ev(f"p{i}", completed=False) for i in range(3)] + [
        _ev(f"c{i}") for i in range(2)
    ]
    res = _classify(tasks, events)
    e = _of(res, DriftType.TOPIC_AVOIDANCE)
    assert e.evidence.affected_categories == [C.PRACTICE]
    assert DriftType.LOW_ENGAGEMENT not in _types(res)  # only one category lags


def test_topic_avoidance_count_boundary() -> None:
    # only 2 avoided in the lagging category -> below the 3 threshold
    tasks = [_task(f"p{i}", C.PRACTICE) for i in range(3)] + [
        _task(f"c{i}", C.CONCEPT_REVIEW) for i in range(2)
    ]
    events = [_ev("p0", completed=False), _ev("p1", completed=False), _ev("p2")] + [
        _ev(f"c{i}") for i in range(2)
    ]
    assert DriftType.TOPIC_AVOIDANCE not in _types(_classify(tasks, events))


def test_topic_avoidance_requires_another_category_progressing() -> None:
    # every category lags -> this is disengagement, not avoidance of one topic
    tasks = [_task(f"p{i}", C.PRACTICE) for i in range(3)] + [
        _task(f"c{i}", C.CONCEPT_REVIEW) for i in range(3)
    ]
    events = [_ev(f"p{i}", completed=False) for i in range(3)] + [
        _ev(f"c{i}", completed=False) for i in range(3)
    ]
    assert DriftType.TOPIC_AVOIDANCE not in _types(_classify(tasks, events))


# --------------------------------------------------------------------------- #
# low_engagement
# --------------------------------------------------------------------------- #


def test_low_engagement_triggers_across_many_categories() -> None:
    cats = [C.PRACTICE, C.CONCEPT_REVIEW, C.PROJECT]
    tasks = [_task(f"t{i}", cats[i % 3]) for i in range(6)]
    events = [_ev(f"t{i}", completed=False) for i in range(6)]  # all skipped
    res = _classify(tasks, events)
    e = _of(res, DriftType.LOW_ENGAGEMENT)
    assert e.evidence.trigger_metric == "incomplete_rate"


def test_low_engagement_category_breadth_boundary() -> None:
    # misses span only 2 categories -> below the 3-category breadth floor
    tasks = [_task(f"p{i}", C.PRACTICE) for i in range(2)] + [
        _task(f"c{i}", C.CONCEPT_REVIEW) for i in range(2)
    ]
    events = [_ev(t.task_id, completed=False) for t in tasks]
    assert DriftType.LOW_ENGAGEMENT not in _types(_classify(tasks, events))


def test_low_engagement_skip_rate_boundary_is_inclusive() -> None:
    # exactly 50% skipped, across 3 categories -> fires (rule is >=)
    miss_cats = [C.PRACTICE, C.CONCEPT_REVIEW, C.PROJECT]
    done_cats = [C.MOCK_INTERVIEW, C.REVIEW, C.REFLECTION]
    tasks = [_task(f"m{i}", miss_cats[i]) for i in range(3)] + [
        _task(f"d{i}", done_cats[i]) for i in range(3)
    ]
    events = [_ev(f"m{i}", completed=False) for i in range(3)] + [
        _ev(f"d{i}") for i in range(3)
    ]
    assert DriftType.LOW_ENGAGEMENT in _types(_classify(tasks, events))

    # just below 50% (3 missed of 8) across 3 categories -> does NOT fire
    # (breadth is satisfied; the skip-rate floor is what fails)
    tasks_b = [_task(f"m{i}", miss_cats[i]) for i in range(3)] + [
        _task(f"d{i}", done_cats[i % 3]) for i in range(5)
    ]
    events_b = [_ev(f"m{i}", completed=False) for i in range(3)] + [
        _ev(f"d{i}") for i in range(5)
    ]
    assert DriftType.LOW_ENGAGEMENT not in _types(_classify(tasks_b, events_b))


# --------------------------------------------------------------------------- #
# dependency_blocked
# --------------------------------------------------------------------------- #


def test_dependency_blocked_triggers_on_missed_prerequisite() -> None:
    tasks = [_task("t1", C.PRACTICE), _task("t2", C.PRACTICE, deps=["t1"])]
    events = [_ev("t1", completed=False)]  # prereq missed; t2 not done
    res = _classify(tasks, events)
    e = _of(res, DriftType.DEPENDENCY_BLOCKED)
    assert e.reason_code is DRIFT_TYPE_TO_REASON_CODE[DriftType.DEPENDENCY_BLOCKED]
    assert e.evidence.trigger_value == 1.0


def test_dependency_not_blocked_when_prerequisite_completed() -> None:
    tasks = [_task("t1", C.PRACTICE), _task("t2", C.PRACTICE, deps=["t1"])]
    events = [_ev("t1")]  # prereq completed -> downstream not blocked
    assert DriftType.DEPENDENCY_BLOCKED not in _types(_classify(tasks, events))


# --------------------------------------------------------------------------- #
# external_conflict
# --------------------------------------------------------------------------- #


def test_external_conflict_triggers_on_reschedule_correlation() -> None:
    tasks = [_task(f"p{i}", C.PRACTICE) for i in range(4)]
    events = [_ev(f"p{i}", completed=False, reschedule=2) for i in range(3)] + [
        _ev("p3", completed=False, reschedule=0)
    ]  # 3/4 misses reschedule-associated -> 0.75 >= 0.5
    res = _classify(tasks, events)
    e = _of(res, DriftType.EXTERNAL_CONFLICT)
    assert e.evidence.trigger_metric == "conflict_associated_miss_ratio"


def test_external_conflict_uses_provided_conflict_ids() -> None:
    tasks = [_task(f"p{i}", C.PRACTICE) for i in range(3)]
    events = [_ev(f"p{i}", completed=False) for i in range(3)]  # no reschedules
    res = _classify(
        tasks, events, external_conflict_task_ids=frozenset({"p0", "p1"})
    )  # 2/3 -> 0.67 >= 0.5
    assert DriftType.EXTERNAL_CONFLICT in _types(res)


def test_external_conflict_min_misses_boundary() -> None:
    tasks = [_task(f"p{i}", C.PRACTICE) for i in range(2)]
    events = [_ev(f"p{i}", completed=False, reschedule=2) for i in range(2)]  # 2 < 3
    assert DriftType.EXTERNAL_CONFLICT not in _types(_classify(tasks, events))


def test_external_conflict_correlation_boundary() -> None:
    tasks = [_task(f"p{i}", C.PRACTICE) for i in range(4)]
    events = [_ev("p0", completed=False, reschedule=2)] + [
        _ev(f"p{i}", completed=False, reschedule=0) for i in range(1, 4)
    ]  # 1/4 = 0.25 < 0.5
    assert DriftType.EXTERNAL_CONFLICT not in _types(_classify(tasks, events))


# --------------------------------------------------------------------------- #
# calendar_fragmentation
# --------------------------------------------------------------------------- #


def test_calendar_fragmentation_triggers() -> None:
    tasks = [_task("d1", C.PROJECT, dur=120, focus=FocusLevel.DEEP)]
    res = _classify(
        tasks, [], fragmentation=FragmentationSignal(total_free_min=300, largest_free_block_min=60)
    )
    e = _of(res, DriftType.CALENDAR_FRAGMENTATION)
    assert e.evidence.trigger_value == 60.0
    assert e.evidence.threshold == 120.0


def test_no_fragmentation_when_largest_block_fits() -> None:
    tasks = [_task("d1", C.PROJECT, dur=120, focus=FocusLevel.DEEP)]
    res = _classify(
        tasks, [], fragmentation=FragmentationSignal(total_free_min=300, largest_free_block_min=120)
    )
    assert DriftType.CALENDAR_FRAGMENTATION not in _types(res)


def test_no_fragmentation_without_signal_or_deep_tasks() -> None:
    deep = [_task("d1", C.PROJECT, dur=120, focus=FocusLevel.DEEP)]
    assert DriftType.CALENDAR_FRAGMENTATION not in _types(_classify(deep, []))
    # signal present but no deep-work tasks
    medium = [_task("m1", C.PRACTICE, dur=120, focus=FocusLevel.MEDIUM)]
    res = _classify(
        medium, [], fragmentation=FragmentationSignal(total_free_min=300, largest_free_block_min=30)
    )
    assert DriftType.CALENDAR_FRAGMENTATION not in _types(res)


# --------------------------------------------------------------------------- #
# cross-cutting
# --------------------------------------------------------------------------- #


def test_clean_telemetry_produces_no_drift() -> None:
    tasks = [_task(f"p{i}", C.PRACTICE) for i in range(5)]
    events = [_ev(f"p{i}", sched=90, actual=90) for i in range(5)]  # ratio 1.0
    assert _classify(tasks, events) == []


def test_every_event_reason_code_matches_type_and_confidence_in_range() -> None:
    # a scenario that fires several drift types at once
    tasks = [_task(f"p{i}", C.PRACTICE) for i in range(5)]
    events = [_ev(f"p{i}", sched=90, actual=135) for i in range(5)]  # duration drift
    res = _classify(
        tasks,
        events,
        weekly_cycles=[WeeklyCapacity(600, 200), WeeklyCapacity(600, 100)],  # capacity
    )
    assert {DriftType.CAPACITY_MISMATCH, DriftType.DURATION_UNDERESTIMATE} <= _types(res)
    for e in res:
        assert e.reason_code is DRIFT_TYPE_TO_REASON_CODE[e.drift_type]
        assert 0.5 <= e.confidence <= 1.0
        assert e.plan_version == "pv1"
        assert e.detected_at == TS


def test_output_is_canonically_ordered_and_deterministic() -> None:
    tasks = [_task(f"p{i}", C.PRACTICE) for i in range(5)]
    events = [_ev(f"p{i}", sched=90, actual=135) for i in range(5)]
    kw = {"weekly_cycles": [WeeklyCapacity(600, 200), WeeklyCapacity(600, 100)]}
    first = _classify(tasks, events, **kw)
    second = _classify(tasks, events, **kw)
    assert [e.drift_type for e in first] == [e.drift_type for e in second]
    # capacity_mismatch (enum index 0) sorts before duration_underestimate (1)
    assert first[0].drift_type is DriftType.CAPACITY_MISMATCH
