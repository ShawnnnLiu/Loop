"""Tests for the deterministic nudge tone tier (Phase 6d).

The tier is selected from ``pressure_tolerance`` by contract derivation —
never by the LLM — and stamped onto every ``NudgeRecord`` so the render lane
(``UserFacingExplanationNode``) phrases within it.
"""

from __future__ import annotations

from zoneinfo import ZoneInfo

import pytest

from agentic_calendar.accountability import (
    NUDGE_TONE_TIER_BY_PRESSURE,
    CheckinStatus,
    NudgeDeliveryService,
    ProjectionInput,
    derive_accountability_contract,
    derive_nudge_tone_tier,
    evaluate_accountability,
)
from agentic_calendar.accountability.nudge_store import InMemoryNudgeStore
from agentic_calendar.common.clock import FrozenClock
from agentic_calendar.common.ids import DeterministicIdGenerator
from agentic_calendar.contracts.motivation_profile import Level
from agentic_calendar.contracts.nudge import NudgeToneTier
from agentic_calendar.contracts.reason_codes import ReasonCode

from ._builders import T0, build_contract, build_profile, build_telemetry_event


@pytest.mark.parametrize(
    ("pressure", "tier"),
    [
        (Level.LOW, NudgeToneTier.GENTLE),
        (Level.MEDIUM, NudgeToneTier.STANDARD),
        (Level.HIGH, NudgeToneTier.DIRECT),
    ],
    ids=lambda v: v.value,
)
def test_tone_tier_mapping_table(pressure: Level, tier: NudgeToneTier) -> None:
    assert derive_nudge_tone_tier(pressure) is tier


def test_mapping_covers_every_level() -> None:
    assert set(NUDGE_TONE_TIER_BY_PRESSURE) == set(Level)
    assert set(NUDGE_TONE_TIER_BY_PRESSURE.values()) == set(NudgeToneTier)


@pytest.mark.parametrize("pressure", list(Level), ids=lambda v: v.value)
def test_derived_contract_carries_tier(pressure: Level) -> None:
    contract = derive_accountability_contract(
        build_profile(pressure_tolerance=pressure),
        id_generator=DeterministicIdGenerator(),
        clock=FrozenClock(T0),
    )
    assert contract.nudge_tone_tier is derive_nudge_tone_tier(pressure)


def test_delivery_stamps_contract_tier_on_record() -> None:
    """End to end through the real engine: the decision's nudge carries the
    contract's tier."""
    contract = build_contract(nudge_tone_tier=NudgeToneTier.DIRECT)
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
    assert outcome.decision.reason_code is ReasonCode.MISSED_TASK_THRESHOLD_REACHED
    service = NudgeDeliveryService(
        clock=FrozenClock(T0),
        id_generator=DeterministicIdGenerator(),
        store=InMemoryNudgeStore(),
    )
    record = service.maybe_deliver(
        decision=outcome.decision, contract=contract, tz=ZoneInfo("America/Los_Angeles")
    )
    assert record is not None
    assert record.tone_tier is NudgeToneTier.DIRECT


def test_tier_values_are_not_psych_labels() -> None:
    """Tier vocabulary stays behavioral; the no-psych-labels suite scans the
    stored surface, this pins the enum itself."""
    forbidden = {"lazy", "irresponsible", "anxious", "avoidant", "unmotivated"}
    assert {t.value for t in NudgeToneTier}.isdisjoint(forbidden)
