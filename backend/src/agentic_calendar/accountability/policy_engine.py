"""Deterministic Accountability Policy Engine (Phase 7).

Spec: ``docs/specs/accountability-intervention.schema.md``; axiom 21
("Accountability Policy Engine"); axiom 12 (decision-first,
explanation-second). Golden scenarios 16, 17, 18, 21, 22, 24.

The engine is pure: the same state, contract, and check-in status always
produce the same decision, and **every** rule evaluation is logged on the
decision (axiom 21). The LLM never evaluates, reorders, or overrides policies.

Two lanes: the private lane is ordered first-match-wins; the sponsor lane is
evaluated independently because a sponsor report is additive to, never a
replacement for, the private intervention (spec "Two Lanes"). An inactive
contract short-circuits both lanes with ``ACCOUNTABILITY_CONTRACT_INACTIVE``
and an empty evaluation list.
"""

from __future__ import annotations

from dataclasses import dataclass

from agentic_calendar.common.clock import Clock
from agentic_calendar.common.ids import IdGenerator
from agentic_calendar.contracts.accountability_contract import AccountabilityContract
from agentic_calendar.contracts.accountability_intervention import (
    AccountabilityAction,
    InterventionDecision,
    PolicyRuleEvaluation,
)
from agentic_calendar.contracts.accountability_state import AccountabilityState
from agentic_calendar.contracts.motivation_profile import SponsorVisibility
from agentic_calendar.contracts.reason_codes import ReasonCode

from .checkin import CheckinStatus
from .projection import ProjectionInput, project_accountability_state

#: Sponsor-lane missed-task floor (axiom 21 policy table; golden scenario 17).
#: Fixed, not user-scaled: external visibility must never get easier to
#: trigger than the axiom's published floor.
SPONSOR_SUMMARY_MISSED_TASK_FLOOR: int = 4


@dataclass(frozen=True)
class _RuleResult:
    evaluation: PolicyRuleEvaluation
    action: AccountabilityAction
    reason_code: ReasonCode


class AccountabilityPolicyEngine:
    """Ordered, auditable, rule-based intervention selection."""

    def __init__(self, *, clock: Clock, id_generator: IdGenerator) -> None:
        self._clock = clock
        self._ids = id_generator

    def decide(
        self,
        state: AccountabilityState,
        contract: AccountabilityContract,
        checkin_status: CheckinStatus,
    ) -> InterventionDecision:
        """Evaluate both lanes and return the auditable decision."""
        if not contract.active:
            return InterventionDecision(
                decision_id=self._ids.new_id("intv"),
                user_id=state.user_id,
                plan_id=state.plan_id,
                contract_id=contract.contract_id,
                action=None,
                reason_code=ReasonCode.ACCOUNTABILITY_CONTRACT_INACTIVE,
                policy_name=None,
                sponsor_action=None,
                sponsor_reason_code=ReasonCode.ACCOUNTABILITY_CONTRACT_INACTIVE,
                evaluations=[],
                decided_at=self._clock.now(),
            )

        private_results = [
            self._missed_task_warning(state, contract),
            self._recovery_plan(state, contract),
            self._weekly_checkin_required(contract, checkin_status),
            self._scope_reduction(state, contract),
        ]
        sponsor_result = self._sponsor_summary(state, contract)

        first_match = next((r for r in private_results if r.evaluation.matched), None)
        return InterventionDecision(
            decision_id=self._ids.new_id("intv"),
            user_id=state.user_id,
            plan_id=state.plan_id,
            contract_id=contract.contract_id,
            action=first_match.action if first_match else None,
            reason_code=first_match.reason_code if first_match else None,
            policy_name=first_match.evaluation.policy_name if first_match else None,
            sponsor_action=(
                AccountabilityAction.GENERATE_SPONSOR_SUMMARY_DRAFT
                if sponsor_result.evaluation.matched
                else None
            ),
            sponsor_reason_code=(
                ReasonCode.SPONSOR_REPORT_PENDING if sponsor_result.evaluation.matched else None
            ),
            evaluations=[r.evaluation for r in private_results] + [sponsor_result.evaluation],
            decided_at=self._clock.now(),
        )

    # -- private-lane rules (axiom 21 table order) -----------------------------

    def _missed_task_warning(
        self, state: AccountabilityState, contract: AccountabilityContract
    ) -> _RuleResult:
        threshold = contract.effective_missed_task_escalation_threshold
        return _RuleResult(
            evaluation=PolicyRuleEvaluation(
                policy_name="missed_task_warning",
                matched=state.missed_tasks_7d >= threshold,
                observed_value=float(state.missed_tasks_7d),
                threshold_value=float(threshold),
            ),
            action=AccountabilityAction.SEND_USER_NUDGE,
            reason_code=ReasonCode.MISSED_TASK_THRESHOLD_REACHED,
        )

    def _recovery_plan(
        self, state: AccountabilityState, contract: AccountabilityContract
    ) -> _RuleResult:
        threshold = contract.effective_behind_schedule_intervention_threshold_pct
        return _RuleResult(
            evaluation=PolicyRuleEvaluation(
                policy_name="recovery_plan",
                matched=state.behind_schedule_percent >= threshold,
                observed_value=float(state.behind_schedule_percent),
                threshold_value=float(threshold),
            ),
            action=AccountabilityAction.GENERATE_RECOVERY_PLAN_DRAFT,
            reason_code=ReasonCode.BEHIND_SCHEDULE_THRESHOLD_REACHED,
        )

    def _weekly_checkin_required(
        self, contract: AccountabilityContract, checkin_status: CheckinStatus
    ) -> _RuleResult:
        """Fires while check-ins are enabled and one is outstanding (due or
        already missed) — the spec condition is "check-ins enabled AND no
        check-in this cycle", so a disabled cadence never prompts even if the
        caller passes an inconsistent status.

        ``observed_value`` is 1.0 when outstanding, 0.0 otherwise, against a
        fixed threshold of 1.0 — the rule is boolean; the numbers keep the
        audit record uniform.
        """
        outstanding = contract.weekly_checkin_enabled and checkin_status in (
            CheckinStatus.DUE,
            CheckinStatus.MISSED,
        )
        return _RuleResult(
            evaluation=PolicyRuleEvaluation(
                policy_name="weekly_checkin_required",
                matched=outstanding,
                observed_value=1.0 if outstanding else 0.0,
                threshold_value=1.0,
            ),
            action=AccountabilityAction.CREATE_WEEKLY_CHECKIN_PROMPT,
            reason_code=(
                ReasonCode.CHECKIN_MISSED
                if checkin_status is CheckinStatus.MISSED
                else ReasonCode.CHECKIN_DUE
            ),
        )

    def _scope_reduction(
        self, state: AccountabilityState, contract: AccountabilityContract
    ) -> _RuleResult:
        floor = contract.low_completion_rate_floor
        return _RuleResult(
            evaluation=PolicyRuleEvaluation(
                policy_name="scope_reduction",
                matched=state.completion_rate_14d < floor,
                observed_value=state.completion_rate_14d,
                threshold_value=floor,
            ),
            action=AccountabilityAction.SUGGEST_SCOPE_REDUCTION,
            reason_code=ReasonCode.LOW_COMPLETION_RATE,
        )

    # -- sponsor lane ----------------------------------------------------------

    def _sponsor_summary(
        self, state: AccountabilityState, contract: AccountabilityContract
    ) -> _RuleResult:
        allowed = (
            contract.sponsor_reporting_allowed
            and contract.sponsor_visibility_level is not SponsorVisibility.NONE
        )
        return _RuleResult(
            evaluation=PolicyRuleEvaluation(
                policy_name="sponsor_summary",
                matched=allowed and state.missed_tasks_7d >= SPONSOR_SUMMARY_MISSED_TASK_FLOOR,
                observed_value=float(state.missed_tasks_7d),
                threshold_value=float(SPONSOR_SUMMARY_MISSED_TASK_FLOOR),
            ),
            action=AccountabilityAction.GENERATE_SPONSOR_SUMMARY_DRAFT,
            reason_code=ReasonCode.SPONSOR_REPORT_PENDING,
        )


@dataclass(frozen=True)
class AccountabilityOutcome:
    """Final state (recommendation filled) plus the decision that filled it."""

    state: AccountabilityState
    decision: InterventionDecision


def evaluate_accountability(
    inp: ProjectionInput,
    contract: AccountabilityContract,
    checkin_status: CheckinStatus,
    *,
    clock: Clock,
    id_generator: IdGenerator,
) -> AccountabilityOutcome:
    """Project, decide, and compose the final state in one deterministic pass.

    The final state is rebuilt through full validation (never ``model_copy``)
    with ``recommended_intervention`` set to the private-lane action.
    """
    engine = AccountabilityPolicyEngine(clock=clock, id_generator=id_generator)
    base = project_accountability_state(inp, contract, checkin_status, clock=clock)
    decision = engine.decide(base, contract, checkin_status)
    final = AccountabilityState.model_validate(
        {**base.model_dump(), "recommended_intervention": decision.action}
    )
    return AccountabilityOutcome(state=final, decision=decision)
