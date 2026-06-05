"""Immutable plan versions + generation history (``docs/axioms/15``).

The active plan is never mutated in place; new work creates a new
``PlanVersion``. ``generation_history`` is append-only and recorded on the
plan version itself.
"""

from .plan_version import (
    GenerationStep,
    GenerationStepRecord,
    LifecycleState,
    PlanVersion,
)
from .replan import RecalibrationProposal, propose_recalibrated_plan
from .store import (
    InMemoryPlanVersionStore,
    MultipleActivePlansError,
    PlanVersionAlreadyExistsError,
    PlanVersionNotFoundError,
    PlanVersionStore,
    PlanVersionStoreError,
)

__all__ = [
    "GenerationStep",
    "GenerationStepRecord",
    "InMemoryPlanVersionStore",
    "LifecycleState",
    "MultipleActivePlansError",
    "PlanVersion",
    "PlanVersionAlreadyExistsError",
    "PlanVersionNotFoundError",
    "PlanVersionStore",
    "PlanVersionStoreError",
    "RecalibrationProposal",
    "propose_recalibrated_plan",
]
