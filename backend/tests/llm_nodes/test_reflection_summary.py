"""Tests for the deterministic Phase 4 reflection-summary node."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from agentic_calendar.contracts.common_types import TaskCategory
from agentic_calendar.contracts.drift_event import (
    DRIFT_TYPE_TO_REASON_CODE,
    DriftEvent,
    DriftEvidence,
    DriftType,
    RecommendedPolicyAction,
)
from agentic_calendar.llm_nodes import DeterministicReflectionSummary
from agentic_calendar.llm_nodes.base import LLMNodeError
from agentic_calendar.llm_nodes.reflection_summary import (
    _ensure_no_psychological_labels,
)

TS = datetime(2026, 5, 12, tzinfo=UTC)


def _drift(
    dt: DriftType,
    *,
    action: RecommendedPolicyAction,
    categories: list[TaskCategory] | None = None,
) -> DriftEvent:
    return DriftEvent(
        drift_event_id=f"drift_{dt.value}",
        plan_version="pv1",
        drift_detected=True,
        drift_type=dt,
        reason_code=DRIFT_TYPE_TO_REASON_CODE[dt],
        confidence=0.8,
        evidence=DriftEvidence(
            trigger_metric="m",
            trigger_value=1.5,
            threshold=1.3,
            sample_size=6,
            affected_categories=categories or [],
        ),
        recommended_policy_action=action,
    detected_at=TS,
    )


def test_no_drift_reports_on_track() -> None:
    out = DeterministicReflectionSummary().run(run_id="r", drift_events=[])
    assert out.summary == "Your plan is on track."
    assert out.detail == []


def test_summary_is_deterministic() -> None:
    events = [
        _drift(
            DriftType.DURATION_UNDERESTIMATE,
            action=RecommendedPolicyAction.INCREASE_DURATION_ESTIMATES_FOR_CATEGORY,
            categories=[TaskCategory.PRACTICE],
        )
    ]
    node = DeterministicReflectionSummary()
    a = node.run(run_id="r1", drift_events=events)
    b = node.run(run_id="r2", drift_events=events)
    assert a.model_dump() == b.model_dump()
    assert "1 adjustment suggested" in a.summary
    assert any("taking longer than planned" in line for line in a.detail)


def test_completion_rate_headline_line() -> None:
    out = DeterministicReflectionSummary().run(
        run_id="r", drift_events=[], completion_rate=0.72
    )
    assert out.detail == ["You've completed 72% of recent scheduled tasks."]


def test_every_drift_type_has_behavior_only_phrasing() -> None:
    actions = {
        DriftType.CAPACITY_MISMATCH: RecommendedPolicyAction.REDUCE_WEEKLY_LOAD,
        DriftType.DURATION_UNDERESTIMATE: RecommendedPolicyAction.INCREASE_DURATION_ESTIMATES_FOR_CATEGORY,
        DriftType.DURATION_OVERESTIMATE: RecommendedPolicyAction.DECREASE_DURATION_ESTIMATES_FOR_CATEGORY,
        DriftType.TOPIC_AVOIDANCE: RecommendedPolicyAction.SPLIT_TOPIC_INTO_SMALLER_TASKS,
        DriftType.EXTERNAL_CONFLICT: RecommendedPolicyAction.RESCHEDULE_AROUND_CONFLICT,
        DriftType.LOW_ENGAGEMENT: RecommendedPolicyAction.ASK_USER_TO_ADJUST_GOAL,
        DriftType.DEPENDENCY_BLOCKED: RecommendedPolicyAction.RESCHEDULE_PREREQUISITE_FIRST,
        DriftType.CALENDAR_FRAGMENTATION: RecommendedPolicyAction.SPLIT_TOPIC_INTO_SMALLER_TASKS,
    }
    category_scoped = {
        DriftType.DURATION_UNDERESTIMATE,
        DriftType.DURATION_OVERESTIMATE,
        DriftType.TOPIC_AVOIDANCE,
    }
    node = DeterministicReflectionSummary()
    for dt, action in actions.items():
        cats = [TaskCategory.PRACTICE] if dt in category_scoped else None
        out = node.run(run_id="r", drift_events=[_drift(dt, action=action, categories=cats)])
        assert len(out.detail) == 1
        assert out.detail[0]  # non-empty phrasing for every type
        # the produced phrasing must itself be free of psychological labels
        _ensure_no_psychological_labels(out.detail[0])


def test_psychological_label_guard_rejects_identity_language() -> None:
    with pytest.raises(LLMNodeError):
        _ensure_no_psychological_labels("You have been lazy this week.")
    # ordinary words near the denylist are unaffected (word-boundary match)
    _ensure_no_psychological_labels("Completion was low; tasks were rescheduled.")
