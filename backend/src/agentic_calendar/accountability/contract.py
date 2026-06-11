"""Deterministic accountability-contract derivation (Phase 7).

Spec: ``docs/specs/accountability-contract.schema.md`` ("Threshold Scaling").

``derive_accountability_contract`` is the pure derivation from a
:class:`MotivationProfile`: same profile in, same effective terms out (modulo
the injected id and clock). Scaling uses **pressure tolerance only** —
``procrastination_risk`` shapes LLM nudge tone and ``self_motivation_level``
sets onboarding defaults; neither touches thresholds, keeping the threshold
path single-knob and auditable. All offsets are heuristic priors until
calibrated.
"""

from __future__ import annotations

from agentic_calendar.common.clock import Clock
from agentic_calendar.common.ids import IdGenerator
from agentic_calendar.contracts.accountability_contract import AccountabilityContract
from agentic_calendar.contracts.motivation_profile import Level, MotivationProfile
from agentic_calendar.contracts.nudge import NudgeToneTier

#: Threshold offset per pressure tolerance (spec scaling table). Low tolerance
#: intervenes later (softer); high tolerance earlier.
_PRESSURE_OFFSET: dict[Level, int] = {
    Level.LOW: 1,
    Level.MEDIUM: 0,
    Level.HIGH: -1,
}

#: Deterministic tone tier per pressure tolerance (spec "Tone Tier", Phase
#: 6d). The LLM renders nudge phrasing within the tier; it never picks one.
NUDGE_TONE_TIER_BY_PRESSURE: dict[Level, NudgeToneTier] = {
    Level.LOW: NudgeToneTier.GENTLE,
    Level.MEDIUM: NudgeToneTier.STANDARD,
    Level.HIGH: NudgeToneTier.DIRECT,
}


def derive_nudge_tone_tier(pressure_tolerance: Level) -> NudgeToneTier:
    """Deterministic ``pressure_tolerance → tone tier`` mapping (Phase 6d)."""
    return NUDGE_TONE_TIER_BY_PRESSURE[pressure_tolerance]

#: ``scope_reduction`` floor (axiom 21 policy table) — heuristic prior.
LOW_COMPLETION_RATE_FLOOR: float = 0.5

#: Hours after the due instant before CHECKIN_DUE becomes CHECKIN_MISSED —
#: heuristic prior.
CHECKIN_GRACE_HOURS: int = 48


def _clamp(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, value))


def derive_accountability_contract(
    profile: MotivationProfile,
    *,
    id_generator: IdGenerator,
    clock: Clock,
    active: bool = True,
) -> AccountabilityContract:
    """Build the effective contract the policy engine reads.

    ``active=False`` derives the deterministic kill-switch contract (golden
    scenario 24): the snapshot stays complete and valid, only interventions
    stop.
    """
    offset = _PRESSURE_OFFSET[profile.pressure_tolerance]
    now = clock.now()
    return AccountabilityContract(
        contract_id=id_generator.new_id("acct"),
        user_id=profile.user_id,
        motivation_profile_id=profile.motivation_profile_id,
        profile_version=profile.profile_version,
        active=active,
        weekly_checkin_enabled=profile.weekly_checkin_enabled,
        weekly_checkin_day=profile.weekly_checkin_day,
        weekly_checkin_time=profile.weekly_checkin_time,
        effective_missed_task_escalation_threshold=_clamp(
            profile.missed_task_escalation_threshold + offset, 1, 14
        ),
        effective_behind_schedule_intervention_threshold_pct=_clamp(
            profile.behind_schedule_intervention_threshold_pct + 5 * offset, 5, 50
        ),
        low_completion_rate_floor=LOW_COMPLETION_RATE_FLOOR,
        checkin_grace_hours=CHECKIN_GRACE_HOURS,
        recovery_mode_preference=profile.recovery_mode_preference,
        sponsor_reporting_allowed=profile.sponsor_enabled,
        sponsor_visibility_level=profile.sponsor_visibility_level,
        sponsor_id=profile.sponsor_id,
        nudge_channel_preference=profile.nudge_channel_preference,
        nudge_tone_tier=derive_nudge_tone_tier(profile.pressure_tolerance),
        quiet_hours=profile.quiet_hours,
        created_at=now,
        updated_at=now,
    )
