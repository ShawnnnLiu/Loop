"""Per-user threshold adaptation (Phase 6d; ADR-0007).

Deterministic adjustment of the contract's *private-lane* effective
thresholds from observed behavior (accountability-contract spec "Threshold
Adaptation"): repeatedly declined interventions — the same caller-derived
``declined_interventions`` observable the drift classifier reads — raise the
private nudge thresholds within the derivation clamps, so a user who keeps
declining gets nudged less aggressively instead of being nagged harder.

The policy engine is untouched: it reads effective thresholds exactly as
before, so equal thresholds produce identical decisions. The sponsor floor
of 4 is a policy-engine constant and is structurally out of reach here.
Adaptation produces a new contract snapshot rebuilt through full validation
(house rule: never ``model_copy`` past validators); the prior snapshot is
never mutated. All offsets and decline boundaries are heuristic priors.
"""

from __future__ import annotations

from dataclasses import dataclass

from agentic_calendar.common.clock import Clock
from agentic_calendar.common.ids import IdGenerator
from agentic_calendar.contracts.accountability_contract import AccountabilityContract

#: Decline-count boundaries → (missed-task offset, behind-schedule-pct offset).
#: 2+ declines soften by one step; 4+ by two (the cap). Heuristic priors.
_ADAPTATION_STEPS: tuple[tuple[int, int, int], ...] = (
    (4, 2, 10),
    (2, 1, 5),
)

#: Derivation clamps (accountability-contract spec).
_MISSED_TASK_BAND = (1, 14)
_BEHIND_PCT_BAND = (5, 50)


def _clamp(value: int, band: tuple[int, int]) -> int:
    return max(band[0], min(band[1], value))


@dataclass(frozen=True)
class ThresholdAdaptation:
    """Auditable outcome of one adaptation pass.

    ``contract`` is the new snapshot the policy engine should read next;
    when nothing changed it is the input contract unchanged (same id), so
    a no-op adaptation leaves no spurious snapshot behind.
    """

    contract: AccountabilityContract
    declined_interventions: int
    missed_task_offset: int
    behind_schedule_pct_offset: int
    previous_missed_task_threshold: int
    previous_behind_schedule_threshold_pct: int

    @property
    def changed(self) -> bool:
        return self.contract.effective_missed_task_escalation_threshold != (
            self.previous_missed_task_threshold
        ) or self.contract.effective_behind_schedule_intervention_threshold_pct != (
            self.previous_behind_schedule_threshold_pct
        )


def adapt_contract_thresholds(
    contract: AccountabilityContract,
    *,
    declined_interventions: int,
    id_generator: IdGenerator,
    clock: Clock,
) -> ThresholdAdaptation:
    """Adapt the private-lane thresholds to observed declines, clamped.

    Deterministic: same contract and count in, same effective terms out
    (modulo the injected id and clock). Returns the input contract untouched
    when the offsets produce no movement (already at the clamp, or fewer
    than two declines).
    """
    if declined_interventions < 0:
        raise ValueError("declined_interventions must be >= 0")

    missed_offset, pct_offset = 0, 0
    for boundary, missed_step, pct_step in _ADAPTATION_STEPS:
        if declined_interventions >= boundary:
            missed_offset, pct_offset = missed_step, pct_step
            break

    previous_missed = contract.effective_missed_task_escalation_threshold
    previous_pct = contract.effective_behind_schedule_intervention_threshold_pct
    new_missed = _clamp(previous_missed + missed_offset, _MISSED_TASK_BAND)
    new_pct = _clamp(previous_pct + pct_offset, _BEHIND_PCT_BAND)

    if new_missed == previous_missed and new_pct == previous_pct:
        adapted = contract
    else:
        now = clock.now()
        # Rebuild through the model so every contract invariant re-runs;
        # model_copy(update=...) would skip the validators (house rule).
        adapted = AccountabilityContract.model_validate(
            contract.model_dump()
            | {
                "contract_id": id_generator.new_id("acct"),
                "effective_missed_task_escalation_threshold": new_missed,
                "effective_behind_schedule_intervention_threshold_pct": new_pct,
                "created_at": now,
                "updated_at": now,
            }
        )
    return ThresholdAdaptation(
        contract=adapted,
        declined_interventions=declined_interventions,
        missed_task_offset=missed_offset,
        behind_schedule_pct_offset=pct_offset,
        previous_missed_task_threshold=previous_missed,
        previous_behind_schedule_threshold_pct=previous_pct,
    )
