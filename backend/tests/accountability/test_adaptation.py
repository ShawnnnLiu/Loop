"""Tests for per-user threshold adaptation (Phase 6d).

Phase plan guarantees: clamps hold, adaptation is deterministic and audited,
the policy engine is untouched (same effective thresholds → identical
decisions), and the sponsor floor stays fixed (pinned separately by
``test_sponsor_floor_is_fixed_not_contract_scaled``).
"""

from __future__ import annotations

import pytest

from agentic_calendar.accountability import (
    CheckinStatus,
    ProjectionInput,
    adapt_contract_thresholds,
    evaluate_accountability,
)
from agentic_calendar.common.clock import FrozenClock
from agentic_calendar.common.ids import DeterministicIdGenerator

from ._builders import T0, build_contract, build_telemetry_event


def _adapt(contract, declines: int):
    return adapt_contract_thresholds(
        contract,
        declined_interventions=declines,
        id_generator=DeterministicIdGenerator(),
        clock=FrozenClock(T0),
    )


def test_zero_or_one_decline_is_a_no_op() -> None:
    contract = build_contract()
    for declines in (0, 1):
        result = _adapt(contract, declines)
        assert result.changed is False
        assert result.contract is contract  # no spurious snapshot
        assert result.missed_task_offset == 0
        assert result.behind_schedule_pct_offset == 0


def test_two_declines_soften_by_one_step() -> None:
    contract = build_contract()  # thresholds 2 / 20
    result = _adapt(contract, 2)
    assert result.changed is True
    assert result.contract.effective_missed_task_escalation_threshold == 3
    assert result.contract.effective_behind_schedule_intervention_threshold_pct == 25
    assert result.contract.contract_id != contract.contract_id
    # The prior snapshot is untouched.
    assert contract.effective_missed_task_escalation_threshold == 2


def test_four_declines_soften_by_two_steps_capped() -> None:
    contract = build_contract()
    for declines in (4, 9):  # the cap holds however many declines pile up
        result = _adapt(contract, declines)
        assert result.contract.effective_missed_task_escalation_threshold == 4
        assert (
            result.contract.effective_behind_schedule_intervention_threshold_pct == 30
        )
        assert result.missed_task_offset == 2
        assert result.behind_schedule_pct_offset == 10


def test_boundary_three_declines_stays_one_step() -> None:
    result = _adapt(build_contract(), 3)
    assert result.missed_task_offset == 1


def test_adaptation_clamps_at_band_edges() -> None:
    at_max = build_contract(
        effective_missed_task_escalation_threshold=14,
        effective_behind_schedule_intervention_threshold_pct=50,
    )
    result = _adapt(at_max, 4)
    assert result.changed is False
    assert result.contract is at_max
    near_max = build_contract(
        effective_missed_task_escalation_threshold=13,
        effective_behind_schedule_intervention_threshold_pct=45,
    )
    clamped = _adapt(near_max, 4)
    assert clamped.contract.effective_missed_task_escalation_threshold == 14
    assert clamped.contract.effective_behind_schedule_intervention_threshold_pct == 50


def test_negative_declines_rejected() -> None:
    with pytest.raises(ValueError, match=">= 0"):
        _adapt(build_contract(), -1)


def test_adaptation_is_deterministic_and_audited() -> None:
    a = _adapt(build_contract(), 2)
    b = _adapt(build_contract(), 2)
    assert a.contract == b.contract
    assert a.declined_interventions == 2
    assert a.previous_missed_task_threshold == 2
    assert a.previous_behind_schedule_threshold_pct == 20


def _decide(contract):
    """Run the untouched policy engine against a fixed behind-schedule state."""
    events = [
        build_telemetry_event(f"t{i}", completed=i < 3, user_reschedule_count=0)
        for i in range(8)
    ]
    outcome = evaluate_accountability(
        ProjectionInput(
            user_id="user_123",
            plan_id="plan_004",
            events_7d=events,
            events_14d=events,
            scheduled_minutes_due=360,
            completed_minutes_due=240,
        ),
        contract,
        CheckinStatus.NOT_REQUIRED,
        clock=FrozenClock(T0),
        id_generator=DeterministicIdGenerator(),
    )
    return outcome.decision


def test_same_effective_thresholds_produce_identical_decisions() -> None:
    """Regression vs the Phase 7 engine: adaptation only moves thresholds;
    a contract with equal thresholds decides identically, adapted or not."""
    baseline = build_contract(
        effective_missed_task_escalation_threshold=3,
        effective_behind_schedule_intervention_threshold_pct=25,
    )
    adapted = _adapt(build_contract(), 2).contract  # also 3 / 25
    decision_a = _decide(baseline)
    decision_b = _decide(adapted)
    assert decision_a.action == decision_b.action
    assert decision_a.reason_code == decision_b.reason_code
    assert decision_a.sponsor_action == decision_b.sponsor_action
    assert [
        (e.policy_name, e.matched, e.observed_value, e.threshold_value)
        for e in decision_a.evaluations
    ] == [
        (e.policy_name, e.matched, e.observed_value, e.threshold_value)
        for e in decision_b.evaluations
    ]


def test_adaptation_raises_threshold_past_trigger() -> None:
    """The behavioral point of adaptation: a state that triggered the
    missed-task warning under the old threshold no longer does after two
    declines raised it."""
    before = build_contract(effective_missed_task_escalation_threshold=5)
    after = _adapt(build_contract(effective_missed_task_escalation_threshold=5), 2)
    assert after.contract.effective_missed_task_escalation_threshold == 6
    decision_before = _decide(before)
    decision_after = _decide(after.contract)
    # 5 misses meets threshold 5 but not 6.
    assert decision_before.action is not None
    assert decision_after.action is None or (
        decision_after.reason_code != decision_before.reason_code
    )
