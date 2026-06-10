"""``drift_event`` contract.

Canonical spec: ``docs/specs/drift-event.schema.md`` (axiom 07).

:class:`DriftEvent` is the deterministic classification that the active plan no
longer matches the user's execution reality. The MVP classifier
(``drift/classifier.py``) is rule-based; an LLM may *explain* a drift event but
must never produce one. Every emitted event is a *detected* drift — the absence
of drift is an empty classifier result, not a ``drift_detected: false`` record.

Determinism guarantees enforced here:

* ``confidence`` is a number in ``[0, 1]`` (never an LLM string).
* ``reason_code`` must be the code that corresponds 1:1 to ``drift_type``
  (the mapping is :data:`DRIFT_TYPE_TO_REASON_CODE`, exported so the
  classifier stays the single source and never re-derives it). Phase 4 types
  use the ``DRIFT_*`` family; the Phase 7 accountability-coupled types use the
  accountability-family codes.
* ``evidence`` always names the metric / threshold / sample size that fired.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .common_types import TaskCategory
from .reason_codes import ReasonCode


class DriftType(StrEnum):
    """Allowed drift classifications (drift-event spec).

    The two accountability-coupled types in axiom 07
    (``accountability_mismatch``, ``sponsor_pressure_mismatch``) are
    deliberately excluded — they belong to the Phase 7 Accountability Policy
    Engine, not the MVP drift classifier.
    """

    CAPACITY_MISMATCH = "capacity_mismatch"
    DURATION_UNDERESTIMATE = "duration_underestimate"
    DURATION_OVERESTIMATE = "duration_overestimate"
    TOPIC_AVOIDANCE = "topic_avoidance"
    EXTERNAL_CONFLICT = "external_conflict"
    LOW_ENGAGEMENT = "low_engagement"
    DEPENDENCY_BLOCKED = "dependency_blocked"
    CALENDAR_FRAGMENTATION = "calendar_fragmentation"
    # Accountability-coupled types (Phase 7) — observable behavior only; the
    # classifier never reads the motivation profile.
    ACCOUNTABILITY_MISMATCH = "accountability_mismatch"
    SPONSOR_PRESSURE_MISMATCH = "sponsor_pressure_mismatch"


class RecommendedPolicyAction(StrEnum):
    """Deterministic next action the policy layer attaches to a drift event.

    The full Accountability Policy Engine is Phase 7; ``drift/policy.py`` owns
    the minimal MVP ``drift_type → action`` mapping.
    """

    REDUCE_WEEKLY_LOAD = "reduce_weekly_load"
    EXTEND_TIMELINE = "extend_timeline"
    INCREASE_DURATION_ESTIMATES_FOR_CATEGORY = "increase_duration_estimates_for_category"
    DECREASE_DURATION_ESTIMATES_FOR_CATEGORY = "decrease_duration_estimates_for_category"
    ADD_REVIEW_BLOCK = "add_review_block"
    SPLIT_TOPIC_INTO_SMALLER_TASKS = "split_topic_into_smaller_tasks"
    RESCHEDULE_AROUND_CONFLICT = "reschedule_around_conflict"
    RESCHEDULE_PREREQUISITE_FIRST = "reschedule_prerequisite_first"
    ASK_USER_TO_ADJUST_GOAL = "ask_user_to_adjust_goal"
    REVISE_ACCOUNTABILITY_CONTRACT = "revise_accountability_contract"
    SWITCH_TO_PRIVATE_RECOVERY = "switch_to_private_recovery"


#: 1:1 map from ``drift_type`` to its ``DRIFT_*`` reason code. Exported so the
#: classifier and the contract validator share one source of truth.
DRIFT_TYPE_TO_REASON_CODE: Mapping[DriftType, ReasonCode] = MappingProxyType(
    {
        DriftType.CAPACITY_MISMATCH: ReasonCode.DRIFT_CAPACITY_MISMATCH,
        DriftType.DURATION_UNDERESTIMATE: ReasonCode.DRIFT_DURATION_UNDERESTIMATE,
        DriftType.DURATION_OVERESTIMATE: ReasonCode.DRIFT_DURATION_OVERESTIMATE,
        DriftType.TOPIC_AVOIDANCE: ReasonCode.DRIFT_TOPIC_AVOIDANCE,
        DriftType.EXTERNAL_CONFLICT: ReasonCode.DRIFT_EXTERNAL_CONFLICT,
        DriftType.LOW_ENGAGEMENT: ReasonCode.DRIFT_LOW_ENGAGEMENT,
        DriftType.DEPENDENCY_BLOCKED: ReasonCode.DRIFT_DEPENDENCY_BLOCKED,
        DriftType.CALENDAR_FRAGMENTATION: ReasonCode.DRIFT_CALENDAR_FRAGMENTATION,
        # Accountability-coupled types use the accountability-family codes
        # (ACCOUNTABILITY_MISMATCH is canonical in axiom 16; see drift-event spec).
        DriftType.ACCOUNTABILITY_MISMATCH: ReasonCode.ACCOUNTABILITY_MISMATCH,
        DriftType.SPONSOR_PRESSURE_MISMATCH: ReasonCode.SPONSOR_PRESSURE_MISMATCH,
    }
)

#: Drift types whose evidence must name the affected ``TaskCategory`` values.
_CATEGORY_SCOPED: frozenset[DriftType] = frozenset(
    {
        DriftType.DURATION_UNDERESTIMATE,
        DriftType.DURATION_OVERESTIMATE,
        DriftType.TOPIC_AVOIDANCE,
    }
)


class DriftEvidence(BaseModel):
    """Uniform, validateable evidence for one drift classification.

    Every drift type explains itself the same way: a ``trigger_metric`` whose
    ``trigger_value`` crossed ``threshold`` over ``sample_size`` samples,
    optionally scoped to ``affected_categories``.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    trigger_metric: str = Field(min_length=1)
    trigger_value: float
    threshold: float
    sample_size: int = Field(ge=0)
    affected_categories: list[TaskCategory] = Field(default_factory=list)


class DriftEvent(BaseModel):
    """A single detected, deterministically-classified plan drift."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    drift_event_id: str = Field(min_length=1)
    plan_version: str = Field(min_length=1)
    drift_detected: bool
    drift_type: DriftType
    reason_code: ReasonCode
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: DriftEvidence
    recommended_policy_action: RecommendedPolicyAction
    detected_at: datetime

    @model_validator(mode="after")
    def _always_detected(self) -> DriftEvent:
        if not self.drift_detected:
            raise ValueError(
                "a DriftEvent always represents a detected drift "
                "(drift_detected must be true); absence of drift is an empty "
                "classifier result, not a drift_detected=false event"
            )
        return self

    @model_validator(mode="after")
    def _reason_code_matches_type(self) -> DriftEvent:
        expected = DRIFT_TYPE_TO_REASON_CODE[self.drift_type]
        if self.reason_code is not expected:
            raise ValueError(
                f"reason_code {self.reason_code.value!r} does not match "
                f"drift_type {self.drift_type.value!r}; expected "
                f"{expected.value!r}"
            )
        return self

    @model_validator(mode="after")
    def _category_scoped_has_categories(self) -> DriftEvent:
        if self.drift_type in _CATEGORY_SCOPED and not self.evidence.affected_categories:
            raise ValueError(
                f"drift_type {self.drift_type.value!r} is category-scoped and "
                "requires non-empty evidence.affected_categories"
            )
        return self

    @model_validator(mode="after")
    def _detected_at_aware(self) -> DriftEvent:
        if self.detected_at.tzinfo is None:
            raise ValueError("detected_at must be timezone-aware")
        return self
