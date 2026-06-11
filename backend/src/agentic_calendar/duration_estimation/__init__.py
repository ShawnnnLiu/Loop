"""Duration-estimation kernel (Phase 4; pooled estimator added in Phase 6b).

A small, deterministic shared kernel — like ``prerequisites`` — that any region
may import and that imports no region itself (``.importlinter``: depends on
``common`` and ``contracts`` only).

Phase 4 job: apply learned per-category duration multipliers
(:class:`~agentic_calendar.contracts.user_duration_multipliers.UserDurationMultipliers`)
to a task plan *deterministically*, before validation/scheduling, producing a
new plan plus the plan-diff building blocks that explain the change with the
``USER_DURATION_CALIBRATION`` reason code (axiom 17). The LLM never touches
duration; this keeps the calibrated estimate auditable and out of the
control plane.

Phase 6b adds the consent-gated pooled estimator (ADR-0007): pure training of
the :class:`~agentic_calendar.contracts.pooled_duration_model.PooledDurationModel`
artifact over composition-root-supplied inputs (this kernel imports neither
``telemetry/`` nor ``consent/``), and the deterministic serving fallback
chain — pooled → per-user category multiplier → heuristic baseline — whose
output feeds the same Phase 4 transform on the replan path.
"""

from .pooled import (
    DEFAULT_POOLED_SERVING_CONFIG,
    DEFAULT_POOLED_TRAINING_CONFIG,
    DurationResolution,
    DurationSource,
    PooledServingConfig,
    PooledTrainingConfig,
    PooledTrainingInput,
    derive_completion_rate_band,
    derive_multiplier_band,
    derive_time_of_day_band,
    resolve_duration_multiplier,
    resolve_effective_multipliers,
    train_pooled_model,
)
from .power_user import (
    DEFAULT_ELIGIBILITY_CONFIG,
    DEFAULT_REFINEMENT_CONFIG,
    EligibilityConfig,
    RefinementConfig,
    WeeklyActivity,
    evaluate_power_user_eligibility,
    train_per_user_refinement,
)
from .transform import CalibrationResult, apply_duration_calibration

__all__ = [
    "DEFAULT_ELIGIBILITY_CONFIG",
    "DEFAULT_POOLED_SERVING_CONFIG",
    "DEFAULT_POOLED_TRAINING_CONFIG",
    "DEFAULT_REFINEMENT_CONFIG",
    "CalibrationResult",
    "DurationResolution",
    "DurationSource",
    "EligibilityConfig",
    "PooledServingConfig",
    "PooledTrainingConfig",
    "PooledTrainingInput",
    "RefinementConfig",
    "WeeklyActivity",
    "apply_duration_calibration",
    "derive_completion_rate_band",
    "derive_multiplier_band",
    "derive_time_of_day_band",
    "evaluate_power_user_eligibility",
    "resolve_duration_multiplier",
    "resolve_effective_multipliers",
    "train_per_user_refinement",
    "train_pooled_model",
]
