"""Tests for ``derive_accountability_contract`` (spec "Threshold Scaling")."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from agentic_calendar.accountability.contract import derive_accountability_contract
from agentic_calendar.common.clock import FrozenClock
from agentic_calendar.common.ids import DeterministicIdGenerator
from agentic_calendar.contracts.motivation_profile import Level

from ._builders import build_profile

T = datetime(2026, 5, 10, 19, 0, tzinfo=UTC)


def _derive(profile: object, **kw: object) -> object:
    return derive_accountability_contract(
        profile,  # type: ignore[arg-type]
        id_generator=DeterministicIdGenerator(),
        clock=FrozenClock(T),
        **kw,  # type: ignore[arg-type]
    )


@pytest.mark.parametrize(
    ("tolerance", "expected_missed", "expected_behind"),
    [
        (Level.LOW, 3, 25),
        (Level.MEDIUM, 2, 20),
        (Level.HIGH, 1, 15),
    ],
)
def test_pressure_tolerance_scales_thresholds(
    tolerance: Level, expected_missed: int, expected_behind: int
) -> None:
    contract = _derive(build_profile(pressure_tolerance=tolerance))
    assert contract.effective_missed_task_escalation_threshold == expected_missed
    assert contract.effective_behind_schedule_intervention_threshold_pct == expected_behind


def test_scaling_clamps_to_profile_ranges() -> None:
    floor = _derive(
        build_profile(
            pressure_tolerance=Level.HIGH,
            missed_task_escalation_threshold=1,
            behind_schedule_intervention_threshold_pct=5,
        )
    )
    assert floor.effective_missed_task_escalation_threshold == 1
    assert floor.effective_behind_schedule_intervention_threshold_pct == 5

    ceiling = _derive(
        build_profile(
            pressure_tolerance=Level.LOW,
            missed_task_escalation_threshold=14,
            behind_schedule_intervention_threshold_pct=50,
        )
    )
    assert ceiling.effective_missed_task_escalation_threshold == 14
    assert ceiling.effective_behind_schedule_intervention_threshold_pct == 50


def test_procrastination_risk_never_touches_thresholds() -> None:
    """Risk shapes nudge tone only; the threshold path is single-knob."""
    low = _derive(build_profile(procrastination_risk=Level.LOW))
    high = _derive(build_profile(procrastination_risk=Level.HIGH))
    assert (
        low.effective_missed_task_escalation_threshold
        == high.effective_missed_task_escalation_threshold
    )
    assert (
        low.effective_behind_schedule_intervention_threshold_pct
        == high.effective_behind_schedule_intervention_threshold_pct
    )


def test_snapshot_copies_profile_surface() -> None:
    profile = build_profile()
    contract = _derive(profile)
    assert contract.user_id == profile.user_id
    assert contract.profile_version == profile.profile_version
    assert contract.sponsor_reporting_allowed is profile.sponsor_enabled
    assert contract.sponsor_visibility_level is profile.sponsor_visibility_level
    assert contract.sponsor_id == profile.sponsor_id
    assert contract.nudge_channel_preference is profile.nudge_channel_preference
    assert contract.quiet_hours == profile.quiet_hours
    assert contract.recovery_mode_preference is profile.recovery_mode_preference


def test_inactive_derivation_is_complete_and_valid() -> None:
    """Scenario 24: the kill switch is ``active``, not a degraded shape."""
    contract = _derive(build_profile(), active=False)
    assert contract.active is False
    assert contract.sponsor_reporting_allowed is True


def test_derivation_is_deterministic() -> None:
    profile = build_profile()
    a = _derive(profile)
    b = _derive(profile)
    assert a == b
