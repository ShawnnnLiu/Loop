"""Drift region (Phase 4).

The deterministic, rule-based drift classifier (axiom 07). It reads
:class:`~agentic_calendar.contracts.telemetry.TelemetryEvent` objects and a
:class:`~agentic_calendar.contracts.task_plan.TaskPlan` (passed in by the
caller, never imported from the ``telemetry`` region) and emits zero or more
:class:`~agentic_calendar.contracts.drift_event.DriftEvent` records.

An LLM may *explain* a drift event to the user; it must never classify drift in
the MVP. Every threshold here is an uncalibrated heuristic prior (see
``thresholds.py``).

Leaf region: depends only on ``common``, ``contracts``, and the
``prerequisites`` kernel (reused for ``dependency_blocked``).
"""

from .classifier import DriftClassifier, DriftInput, FragmentationSignal, WeeklyCapacity
from .policy import DRIFT_TYPE_TO_ACTION
from .thresholds import DEFAULT_DRIFT_THRESHOLDS, DriftThresholds

__all__ = [
    "DEFAULT_DRIFT_THRESHOLDS",
    "DRIFT_TYPE_TO_ACTION",
    "DriftClassifier",
    "DriftInput",
    "DriftThresholds",
    "FragmentationSignal",
    "WeeklyCapacity",
]
