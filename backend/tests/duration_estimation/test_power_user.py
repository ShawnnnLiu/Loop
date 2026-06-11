"""Tests for the power-user gate and per-user refinement (Phase 6c).

Phase plan guarantees: every threshold boundary (199/200, 29/30, stability
edge, insufficient weeks); ineligible users get no refinement at training or
serving time; eligibility evaluation is replay-deterministic and fully
logged.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from agentic_calendar.contracts.common_types import ExperienceLevel, TaskCategory
from agentic_calendar.contracts.pooled_duration_model import TimeOfDayBand
from agentic_calendar.contracts.power_user import EligibilityCriterion
from agentic_calendar.contracts.reason_codes import ReasonCode
from agentic_calendar.contracts.telemetry import TelemetryEvent
from agentic_calendar.duration_estimation.pooled import (
    DurationSource,
    resolve_duration_multiplier,
)
from agentic_calendar.duration_estimation.power_user import (
    EligibilityConfig,
    WeeklyActivity,
    evaluate_power_user_eligibility,
    train_per_user_refinement,
)

T0 = datetime(2026, 6, 10, 16, 0, tzinfo=UTC)

_STABLE_WEEKS = [WeeklyActivity(scheduled_count=10, completed_count=8) for _ in range(6)]


def _evaluate(
    *,
    total: int = 215,
    in_category: int = 34,
    weeks: list[WeeklyActivity] | None = None,
):
    return evaluate_power_user_eligibility(
        "user_123",
        TaskCategory.PRACTICE,
        total_completed_tasks=total,
        category_completed_tasks=in_category,
        weekly_activity=weeks if weeks is not None else _STABLE_WEEKS,
        evaluated_at=T0,
    )


def _criterion(result, criterion: EligibilityCriterion):
    return next(c for c in result.criteria if c.criterion is criterion)


def test_all_criteria_met_is_eligible() -> None:
    result = _evaluate()
    assert result.eligible is True
    assert all(c.met for c in result.criteria)
    assert result.unmet_reason_codes() == ()


def test_total_completions_boundary_199_vs_200() -> None:
    assert _evaluate(total=199).eligible is False
    assert _evaluate(total=200).eligible is True
    failed = _criterion(_evaluate(total=199), EligibilityCriterion.TOTAL_COMPLETIONS)
    assert failed.reason_code is ReasonCode.POWER_USER_TOTAL_COMPLETIONS_BELOW_THRESHOLD
    assert failed.observed_value == 199.0
    assert failed.threshold_value == 200.0


def test_category_completions_boundary_29_vs_30() -> None:
    assert _evaluate(in_category=29).eligible is False
    assert _evaluate(in_category=30).eligible is True
    failed = _criterion(_evaluate(in_category=29), EligibilityCriterion.CATEGORY_COMPLETIONS)
    assert failed.reason_code is (
        ReasonCode.POWER_USER_CATEGORY_COMPLETIONS_BELOW_THRESHOLD
    )


def test_assessable_weeks_boundary_3_vs_4() -> None:
    three = [WeeklyActivity(10, 8)] * 3
    four = [WeeklyActivity(10, 8)] * 4
    assert _evaluate(weeks=three).eligible is False
    assert _evaluate(weeks=four).eligible is True
    failed = _criterion(_evaluate(weeks=three), EligibilityCriterion.ASSESSABLE_WEEKS)
    assert failed.reason_code is ReasonCode.POWER_USER_INSUFFICIENT_ASSESSABLE_WEEKS
    assert failed.observed_value == 3.0


def test_sparse_weeks_are_not_assessable() -> None:
    """Weeks with < 3 scheduled tasks don't count toward the 4-week floor."""
    weeks = [WeeklyActivity(10, 8)] * 3 + [WeeklyActivity(2, 2)] * 5
    result = _evaluate(weeks=weeks)
    assert _criterion(result, EligibilityCriterion.ASSESSABLE_WEEKS).observed_value == 3.0
    assert result.eligible is False


def test_stability_boundary_at_exact_threshold_passes() -> None:
    """Variance exactly at the clamped threshold is met (inclusive, spec)."""
    # Rates 0.6/0.8 alternating over 4 weeks: mean 0.7, pvariance ~0.01.
    weeks = [WeeklyActivity(10, 6), WeeklyActivity(10, 8)] * 2
    result = _evaluate(weeks=weeks)
    stability = _criterion(result, EligibilityCriterion.COMPLETION_RATE_STABILITY)
    assert stability.observed_value == pytest.approx(0.01)
    assert stability.met is True

    # Inclusive boundary, pinned exactly: threshold set to the observed
    # variance itself -> still met.
    at_boundary = evaluate_power_user_eligibility(
        "user_123",
        TaskCategory.PRACTICE,
        total_completed_tasks=215,
        category_completed_tasks=34,
        weekly_activity=weeks,
        evaluated_at=T0,
        config=EligibilityConfig(
            max_completion_rate_variance=stability.observed_value
        ),
    )
    boundary = _criterion(at_boundary, EligibilityCriterion.COMPLETION_RATE_STABILITY)
    assert boundary.observed_value == boundary.threshold_value
    assert boundary.met is True

    # Rates 0.4/0.8: pvariance ~0.04 > 0.02 -> unstable.
    wild = [WeeklyActivity(10, 4), WeeklyActivity(10, 8)] * 2
    unstable = _evaluate(weeks=wild)
    failed = _criterion(unstable, EligibilityCriterion.COMPLETION_RATE_STABILITY)
    assert failed.observed_value == pytest.approx(0.04)
    assert failed.met is False
    assert failed.reason_code is ReasonCode.POWER_USER_COMPLETION_RATE_UNSTABLE
    assert unstable.eligible is False


def test_under_two_assessable_weeks_stability_defined_as_zero() -> None:
    """One assessable week: stability reports 0.0 (met); the weeks criterion
    carries the sufficiency failure — no double penalty."""
    result = _evaluate(weeks=[WeeklyActivity(10, 5)])
    stability = _criterion(result, EligibilityCriterion.COMPLETION_RATE_STABILITY)
    assert stability.observed_value == 0.0
    assert stability.met is True
    assert result.unmet_reason_codes() == (
        ReasonCode.POWER_USER_INSUFFICIENT_ASSESSABLE_WEEKS,
    )


def test_all_criteria_always_evaluated_no_short_circuit() -> None:
    result = _evaluate(total=0, in_category=0, weeks=[])
    assert len(result.criteria) == 4
    assert result.unmet_reason_codes() == (
        ReasonCode.POWER_USER_TOTAL_COMPLETIONS_BELOW_THRESHOLD,
        ReasonCode.POWER_USER_CATEGORY_COMPLETIONS_BELOW_THRESHOLD,
        ReasonCode.POWER_USER_INSUFFICIENT_ASSESSABLE_WEEKS,
    )


def test_evaluation_is_replay_deterministic() -> None:
    assert _evaluate() == _evaluate()
    assert _evaluate(total=199) == _evaluate(total=199)


# ---------------------------------------------------------------------------
# Refinement training and serving
# ---------------------------------------------------------------------------


def _event(event_id: str, task_id: str, actual: int, ts: str) -> TelemetryEvent:
    return TelemetryEvent.model_validate(
        {
            "telemetry_event_id": event_id,
            "task_id": task_id,
            "scheduled_duration_min": 60,
            "actual_duration_min": actual,
            "completed": True,
            "completion_timestamp": ts,
            "user_reschedule_count": 0,
            "data_quality": "complete",
        }
    )


_EVENING = "2026-06-09T19:30:00-07:00"
_MORNING = "2026-06-09T08:30:00-07:00"


def _events() -> list[TelemetryEvent]:
    evening = [_event(f"ev_{i}", "t_p", 90, _EVENING) for i in range(6)]  # ratio 1.5
    morning = [_event(f"mo_{i}", "t_p", 60, _MORNING) for i in range(6)]  # ratio 1.0
    return [*evening, *morning]


_CATEGORIES = {"t_p": TaskCategory.PRACTICE}


def _refinement(eligible: bool):
    eligibility = _evaluate() if eligible else _evaluate(total=199)
    return train_per_user_refinement(
        _events(),
        _CATEGORIES,
        user_id="user_123",
        timezone="America/Los_Angeles",
        eligibilities=[eligibility],
        computed_at=T0,
    )


def test_refinement_trains_per_category_and_band_for_eligible_user() -> None:
    refinement = _refinement(eligible=True)
    assert len(refinement.entries) == 2
    evening = refinement.lookup(TaskCategory.PRACTICE, TimeOfDayBand.EVENING)
    morning = refinement.lookup(TaskCategory.PRACTICE, TimeOfDayBand.MORNING)
    assert evening is not None and evening.multiplier == 1.5
    assert morning is not None and morning.multiplier == 1.0
    assert evening.sample_size == 6


def test_ineligible_user_trains_no_refinement() -> None:
    refinement = _refinement(eligible=False)
    assert refinement.entries == []


def test_refinement_training_is_replay_deterministic() -> None:
    assert _refinement(eligible=True) == _refinement(eligible=True)


def _serve(refinement, band):
    return resolve_duration_multiplier(
        TaskCategory.PRACTICE,
        experience_level=ExperienceLevel.BEGINNER,
        recent_completion_rate=0.7,
        per_user=None,
        model=None,
        refinement=refinement,
        time_of_day_band=band,
    )


def test_refined_entry_outranks_other_tiers_when_band_known() -> None:
    resolution = _serve(_refinement(eligible=True), TimeOfDayBand.EVENING)
    assert resolution.source is DurationSource.PER_USER_REFINED
    assert resolution.multiplier == 1.5
    assert resolution.fallback_reasons == ()
    assert resolution.debug["source"] == "per_user_refined"


def test_empty_refinement_serves_identically_to_6b() -> None:
    """Ineligible -> empty artifact -> no refined serving; the 6b chain runs
    with the refinement skip recorded."""
    resolution = _serve(_refinement(eligible=False), TimeOfDayBand.EVENING)
    assert resolution.source is DurationSource.HEURISTIC_BASELINE
    assert resolution.fallback_reasons == (
        ReasonCode.PER_USER_REFINEMENT_UNAVAILABLE,
        ReasonCode.POOLED_MODEL_UNAVAILABLE,
    )


def test_unknown_band_skips_refined_tier() -> None:
    resolution = _serve(_refinement(eligible=True), None)
    assert resolution.source is DurationSource.HEURISTIC_BASELINE
    assert ReasonCode.PER_USER_REFINEMENT_UNAVAILABLE in resolution.fallback_reasons


def test_no_refinement_offered_keeps_6b_reasons_unchanged() -> None:
    resolution = resolve_duration_multiplier(
        TaskCategory.PRACTICE,
        experience_level=ExperienceLevel.BEGINNER,
        recent_completion_rate=0.7,
        per_user=None,
        model=None,
    )
    assert resolution.fallback_reasons == (ReasonCode.POOLED_MODEL_UNAVAILABLE,)
