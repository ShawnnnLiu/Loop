"""Tests for the Phase 7 accountability-coupled drift rules (axiom 07).

Golden scenario 23: a user who repeatedly falls behind while rejecting
accountability interventions yields ``accountability_mismatch`` with policy
action ``revise_accountability_contract`` and no sponsor notification.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from agentic_calendar.common.clock import FrozenClock
from agentic_calendar.common.ids import DeterministicIdGenerator
from agentic_calendar.contracts.common_types import TaskCategory
from agentic_calendar.contracts.drift_event import (
    DriftEvent,
    DriftType,
    RecommendedPolicyAction,
)
from agentic_calendar.contracts.reason_codes import ReasonCode
from agentic_calendar.contracts.task_plan import Task, TaskPlan
from agentic_calendar.contracts.telemetry import DataQuality, TelemetryEvent
from agentic_calendar.drift import DriftClassifier, DriftInput

TS = datetime(2026, 5, 12, tzinfo=UTC)


def _task(tid: str) -> Task:
    return Task(
        task_id=tid,
        module_id=f"m_{tid}",
        title=tid,
        estimated_duration_min=60,
        cognitive_load=3,
        category=TaskCategory.PRACTICE,
        required_focus_level="medium",
        dependencies=[],
    )


def _missed(tid: str) -> TelemetryEvent:
    return TelemetryEvent(
        telemetry_event_id=f"tel_{tid}",
        task_id=tid,
        scheduled_duration_min=60,
        actual_duration_min=None,
        completed=False,
        completion_timestamp=None,
        user_reschedule_count=0,
        data_quality=DataQuality.COMPLETE,
    )


def _classify(events: Sequence[TelemetryEvent], **kw: object) -> list[DriftEvent]:
    # TaskPlan requires at least one task; a placeholder keeps event-free
    # scenarios (sponsor-pressure rule) valid.
    tasks = [_task(e.task_id) for e in events] or [_task("t_placeholder")]
    plan = TaskPlan(plan_version="pv1", tasks=tasks)
    clf = DriftClassifier(clock=FrozenClock(TS), id_generator=DeterministicIdGenerator())
    return clf.classify(DriftInput(plan=plan, events=list(events), **kw))  # type: ignore[arg-type]


def _types(events: Sequence[DriftEvent]) -> set[DriftType]:
    return {e.drift_type for e in events}


# -- accountability_mismatch (golden scenario 23) -----------------------------------


def test_scenario_23_repeated_misses_plus_declined_interventions() -> None:
    events = [_missed(f"t{i}") for i in range(3)]
    result = _classify(events, declined_interventions=1)
    assert DriftType.ACCOUNTABILITY_MISMATCH in _types(result)
    event = next(e for e in result if e.drift_type is DriftType.ACCOUNTABILITY_MISMATCH)
    assert event.reason_code is ReasonCode.ACCOUNTABILITY_MISMATCH
    assert event.recommended_policy_action is RecommendedPolicyAction.REVISE_ACCOUNTABILITY_CONTRACT
    # No sponsor notification: the recommended action is a contract revision,
    # never a sponsor draft, and the classifier emits no sponsor-facing code.
    assert all(e.reason_code is not ReasonCode.SPONSOR_REPORT_PENDING for e in result)
    assert event.evidence.trigger_metric == "declined_interventions_with_repeated_misses"
    assert event.evidence.sample_size == 3


def test_no_mismatch_without_declines() -> None:
    events = [_missed(f"t{i}") for i in range(5)]
    result = _classify(events, declined_interventions=0)
    assert DriftType.ACCOUNTABILITY_MISMATCH not in _types(result)


def test_no_mismatch_below_missed_floor() -> None:
    events = [_missed(f"t{i}") for i in range(2)]
    result = _classify(events, declined_interventions=3)
    assert DriftType.ACCOUNTABILITY_MISMATCH not in _types(result)


# -- sponsor_pressure_mismatch --------------------------------------------------------


def test_sponsor_disabled_after_repeated_reports_fires() -> None:
    result = _classify(
        [],
        sponsor_reports_sent_recent=2,
        sponsor_reporting_disabled=True,
    )
    assert _types(result) == {DriftType.SPONSOR_PRESSURE_MISMATCH}
    event = result[0]
    assert event.reason_code is ReasonCode.SPONSOR_PRESSURE_MISMATCH
    assert event.recommended_policy_action is RecommendedPolicyAction.SWITCH_TO_PRIVATE_RECOVERY
    assert event.evidence.trigger_metric == "sponsor_reports_before_disable"


def test_no_pressure_mismatch_while_reporting_active() -> None:
    result = _classify([], sponsor_reports_sent_recent=5)
    assert DriftType.SPONSOR_PRESSURE_MISMATCH not in _types(result)


def test_no_pressure_mismatch_below_report_floor() -> None:
    result = _classify(
        [],
        sponsor_reports_sent_recent=1,
        sponsor_reporting_disabled=True,
    )
    assert DriftType.SPONSOR_PRESSURE_MISMATCH not in _types(result)


# -- determinism ----------------------------------------------------------------------


def test_accountability_rules_replay_identically() -> None:
    events = [_missed(f"t{i}") for i in range(3)]
    a = _classify(events, declined_interventions=2)
    b = _classify(events, declined_interventions=2)
    assert [(e.drift_type, e.confidence, e.evidence) for e in a] == [
        (e.drift_type, e.confidence, e.evidence) for e in b
    ]
