"""Drift-classifier thresholds — UNCALIBRATED HEURISTIC PRIORS (axiom 07).

Every value here was chosen to be *plausible, not optimal*. They will be wrong
for some users and right for others, and there is no data yet to know which.
Per axiom 07 ("Threshold Honesty"), the system must not present drift detection
as tuned or data-driven until calibration runs (>= 50 active users with >= 4
weeks of telemetry each). Treat these as priors pending calibration.

Per-user sensitivity scaling (conservative/balanced/aggressive, axiom 07) is a
later feature: it would multiply these priors before classification without
changing the deterministic rules. Phase 4 ships the balanced defaults only.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DriftThresholds:
    """Deterministic thresholds for each drift rule (heuristic priors)."""

    # duration_underestimate / duration_overestimate (per category)
    duration_underestimate_ratio: float = 1.3
    duration_overestimate_ratio: float = 0.7
    duration_min_sample: int = 5

    # capacity_mismatch (weekly cycles)
    capacity_completion_floor: float = 0.60
    capacity_min_cycles: int = 2

    # topic_avoidance (per category)
    topic_avoidance_min_events: int = 3

    # low_engagement (global)
    low_engagement_skip_rate: float = 0.5
    low_engagement_min_categories: int = 3
    low_engagement_min_sample: int = 4

    # external_conflict (global)
    external_conflict_reschedule_threshold: int = 2
    external_conflict_min_misses: int = 3
    external_conflict_correlation: float = 0.5

    # dependency_blocked (global)
    dependency_blocked_min: int = 1

    # accountability_mismatch (global; Phase 7) — repeated misses plus
    # explicitly declined/ignored accountability interventions
    accountability_min_missed: int = 3
    accountability_min_declined: int = 1

    # sponsor_pressure_mismatch (global; Phase 7) — sponsor reporting disabled
    # after this many reports were sent in the window
    sponsor_pressure_min_reports: int = 2


DEFAULT_DRIFT_THRESHOLDS = DriftThresholds()
