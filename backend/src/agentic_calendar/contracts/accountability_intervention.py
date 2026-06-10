"""``accountability_intervention`` contract.

Canonical spec: ``docs/specs/accountability-intervention.schema.md``
(axiom 21, axiom 12, axiom 16).

:class:`InterventionDecision` is the auditable output of one Accountability
Policy Engine evaluation. Axiom 21 requires that policies are evaluated in
order, the first matching policy chooses the action, and *every* rule
evaluation is logged — :class:`PolicyRuleEvaluation` is that log line.

Two lanes (spec "Two Lanes"): the private lane is ordered first-match-wins;
the sponsor lane (``sponsor_summary``) is evaluated independently because a
sponsor report is additive to, never a replacement for, the private
intervention (golden scenarios 16 vs 17). An inactive contract short-circuits
both lanes with ``ACCOUNTABILITY_CONTRACT_INACTIVE`` and an empty evaluation
list (golden scenario 24).
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .reason_codes import ReasonCode


class AccountabilityAction(StrEnum):
    """Deterministic actions the policy engine may select (axiom 21)."""

    SEND_USER_NUDGE = "send_user_nudge"
    GENERATE_RECOVERY_PLAN_DRAFT = "generate_recovery_plan_draft"
    CREATE_WEEKLY_CHECKIN_PROMPT = "create_weekly_checkin_prompt"
    GENERATE_SPONSOR_SUMMARY_DRAFT = "generate_sponsor_summary_draft"
    SUGGEST_SCOPE_REDUCTION = "suggest_scope_reduction"


#: Private-lane policy names in canonical evaluation order (axiom 21 table).
PRIVATE_LANE_POLICIES: tuple[str, ...] = (
    "missed_task_warning",
    "recovery_plan",
    "weekly_checkin_required",
    "scope_reduction",
)

#: The single sponsor-lane policy name.
SPONSOR_LANE_POLICY: str = "sponsor_summary"

#: Reason codes each private-lane action may legitimately carry. Exported so
#: the engine and the contract validator share one source of truth (same
#: pattern as ``DRIFT_TYPE_TO_REASON_CODE``).
ACTION_TO_REASON_CODES: Mapping[AccountabilityAction, frozenset[ReasonCode]] = MappingProxyType(
    {
        AccountabilityAction.SEND_USER_NUDGE: frozenset({ReasonCode.MISSED_TASK_THRESHOLD_REACHED}),
        AccountabilityAction.GENERATE_RECOVERY_PLAN_DRAFT: frozenset(
            {ReasonCode.BEHIND_SCHEDULE_THRESHOLD_REACHED}
        ),
        AccountabilityAction.CREATE_WEEKLY_CHECKIN_PROMPT: frozenset(
            {ReasonCode.CHECKIN_DUE, ReasonCode.CHECKIN_MISSED}
        ),
        AccountabilityAction.SUGGEST_SCOPE_REDUCTION: frozenset({ReasonCode.LOW_COMPLETION_RATE}),
    }
)


class PolicyRuleEvaluation(BaseModel):
    """Audit record of one policy-rule check (axiom 21: every evaluation logged)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    policy_name: str = Field(min_length=1)
    matched: bool
    observed_value: float
    threshold_value: float


_ALL_POLICIES: tuple[str, ...] = (*PRIVATE_LANE_POLICIES, SPONSOR_LANE_POLICY)


class InterventionDecision(BaseModel):
    """The auditable outcome of one policy-engine evaluation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    decision_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    plan_id: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    action: AccountabilityAction | None = None
    reason_code: ReasonCode | None = None
    policy_name: str | None = None
    sponsor_action: AccountabilityAction | None = None
    sponsor_reason_code: ReasonCode | None = None
    evaluations: list[PolicyRuleEvaluation] = Field(default_factory=list)
    decided_at: datetime

    @model_validator(mode="after")
    def _private_lane_consistency(self) -> InterventionDecision:
        """A private-lane action carries its policy name and a matching code."""
        if self.action is not None:
            if self.policy_name is None or self.reason_code is None:
                raise ValueError("a non-null action requires policy_name and reason_code")
            if self.action is AccountabilityAction.GENERATE_SPONSOR_SUMMARY_DRAFT:
                raise ValueError(
                    "generate_sponsor_summary_draft belongs to the sponsor lane, "
                    "never the private-lane action"
                )
            allowed = ACTION_TO_REASON_CODES[self.action]
            if self.reason_code not in allowed:
                raise ValueError(
                    f"action '{self.action.value}' cannot carry reason_code "
                    f"'{self.reason_code.value}'"
                )
        elif self.policy_name is not None:
            raise ValueError("policy_name must be null when no action was chosen")
        return self

    @model_validator(mode="after")
    def _sponsor_lane_consistency(self) -> InterventionDecision:
        if self.sponsor_action is not None:
            if self.sponsor_action is not AccountabilityAction.GENERATE_SPONSOR_SUMMARY_DRAFT:
                raise ValueError("sponsor_action may only be generate_sponsor_summary_draft")
            if self.sponsor_reason_code is not ReasonCode.SPONSOR_REPORT_PENDING:
                raise ValueError("a fired sponsor lane must carry SPONSOR_REPORT_PENDING")
        elif self.sponsor_reason_code not in (
            None,
            ReasonCode.ACCOUNTABILITY_CONTRACT_INACTIVE,
        ):
            raise ValueError(
                "sponsor_reason_code without a sponsor_action may only be "
                "ACCOUNTABILITY_CONTRACT_INACTIVE"
            )
        return self

    @model_validator(mode="after")
    def _inactive_short_circuit(self) -> InterventionDecision:
        """The inactive contract evaluates (and logs) nothing (scenario 24)."""
        if self.reason_code is ReasonCode.ACCOUNTABILITY_CONTRACT_INACTIVE:
            if self.action is not None:
                raise ValueError("ACCOUNTABILITY_CONTRACT_INACTIVE cannot carry an action")
            if self.evaluations:
                raise ValueError("the inactive short circuit must not evaluate (or log) any rules")
            if self.sponsor_reason_code is not ReasonCode.ACCOUNTABILITY_CONTRACT_INACTIVE:
                raise ValueError("the inactive short circuit applies to both lanes")
        return self

    @model_validator(mode="after")
    def _active_decision_logs_every_rule(self) -> InterventionDecision:
        """Active-contract decisions log all 5 rules in policy-table order."""
        if self.reason_code is ReasonCode.ACCOUNTABILITY_CONTRACT_INACTIVE:
            return self
        names = tuple(e.policy_name for e in self.evaluations)
        if names != _ALL_POLICIES:
            raise ValueError(
                "an active-contract decision must log every policy in canonical "
                f"order {_ALL_POLICIES}, got {names}"
            )
        return self

    @model_validator(mode="after")
    def _no_intervention_means_nothing_matched(self) -> InterventionDecision:
        """action=null + reason=null is only valid when no private rule matched."""
        if self.action is None and self.reason_code is None:
            private = frozenset(PRIVATE_LANE_POLICIES)
            for e in self.evaluations:
                if e.policy_name in private and e.matched:
                    raise ValueError(
                        f"private-lane rule '{e.policy_name}' matched but no action was chosen"
                    )
        return self

    @model_validator(mode="after")
    def _decided_at_aware(self) -> InterventionDecision:
        if self.decided_at.tzinfo is None:
            raise ValueError("decided_at must be timezone-aware")
        return self
