"""Deterministic drift → policy-action mapping (Phase 4).

The MVP picks one primary :class:`RecommendedPolicyAction` per
:class:`DriftType`, following the "Response" column of the axiom 07 drift table.
This is intentionally the *minimal* policy surface: the full Accountability
Policy Engine (axiom 21, Phase 7) decides whether, how, and to whom the system
responds. Centralizing the mapping here keeps the classifier free of action
choices and gives Phase 7 one place to extend.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from agentic_calendar.contracts.drift_event import DriftType, RecommendedPolicyAction

#: One deterministic primary action per drift type (axiom 07 "Response" column).
DRIFT_TYPE_TO_ACTION: Mapping[DriftType, RecommendedPolicyAction] = MappingProxyType(
    {
        DriftType.CAPACITY_MISMATCH: RecommendedPolicyAction.REDUCE_WEEKLY_LOAD,
        DriftType.DURATION_UNDERESTIMATE: (
            RecommendedPolicyAction.INCREASE_DURATION_ESTIMATES_FOR_CATEGORY
        ),
        DriftType.DURATION_OVERESTIMATE: (
            RecommendedPolicyAction.DECREASE_DURATION_ESTIMATES_FOR_CATEGORY
        ),
        DriftType.TOPIC_AVOIDANCE: RecommendedPolicyAction.SPLIT_TOPIC_INTO_SMALLER_TASKS,
        DriftType.EXTERNAL_CONFLICT: RecommendedPolicyAction.RESCHEDULE_AROUND_CONFLICT,
        DriftType.LOW_ENGAGEMENT: RecommendedPolicyAction.ASK_USER_TO_ADJUST_GOAL,
        DriftType.DEPENDENCY_BLOCKED: (
            RecommendedPolicyAction.RESCHEDULE_PREREQUISITE_FIRST
        ),
        DriftType.CALENDAR_FRAGMENTATION: (
            RecommendedPolicyAction.SPLIT_TOPIC_INTO_SMALLER_TASKS
        ),
        # Phase 7 accountability-coupled types (axiom 07 "Response" column;
        # golden scenario 23). The Accountability Policy Engine decides the
        # concrete follow-through; neither ever notifies a sponsor.
        DriftType.ACCOUNTABILITY_MISMATCH: (
            RecommendedPolicyAction.REVISE_ACCOUNTABILITY_CONTRACT
        ),
        DriftType.SPONSOR_PRESSURE_MISMATCH: (
            RecommendedPolicyAction.SWITCH_TO_PRIVATE_RECOVERY
        ),
    }
)
