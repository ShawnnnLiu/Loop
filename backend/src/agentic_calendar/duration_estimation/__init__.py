"""Duration-estimation kernel (Phase 4).

A small, deterministic shared kernel — like ``prerequisites`` — that any region
may import and that imports no region itself (``.importlinter``: depends on
``common`` and ``contracts`` only).

Its single job is to apply learned per-category duration multipliers
(:class:`~agentic_calendar.contracts.user_duration_multipliers.UserDurationMultipliers`)
to a task plan *deterministically*, before validation/scheduling, producing a
new plan plus the plan-diff building blocks that explain the change with the
``USER_DURATION_CALIBRATION`` reason code (axiom 17). The LLM never touches
duration; this keeps the calibrated estimate auditable and out of the
control plane.
"""

from .transform import CalibrationResult, apply_duration_calibration

__all__ = ["CalibrationResult", "apply_duration_calibration"]
