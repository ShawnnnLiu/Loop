"""Tests for the pooled serving fallback chain and plan application.

Phase plan guarantees: pooled hit / sparse bucket / artifact missing /
artifact invalid all resolve deterministically without blocking planning;
opt-out at serving time falls back; the debug payload names the winning
source; plan application creates a new draft version only.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from agentic_calendar.contracts.common_types import ExperienceLevel, TaskCategory
from agentic_calendar.contracts.pooled_duration_model import PooledDurationModel
from agentic_calendar.contracts.reason_codes import ReasonCode
from agentic_calendar.contracts.task_plan import TaskPlan
from agentic_calendar.contracts.telemetry import TelemetryEvent
from agentic_calendar.contracts.user_duration_multipliers import (
    CategoryMultiplier,
    UserDurationMultipliers,
)
from agentic_calendar.duration_estimation.pooled import (
    DurationSource,
    PooledServingConfig,
    PooledTrainingInput,
    resolve_duration_multiplier,
    resolve_effective_multipliers,
    train_pooled_model,
)
from agentic_calendar.duration_estimation.transform import apply_duration_calibration

T0 = datetime(2026, 6, 10, 16, 0, tzinfo=UTC)


def _event(event_id: str, task_id: str, actual: int) -> TelemetryEvent:
    return TelemetryEvent.model_validate(
        {
            "telemetry_event_id": event_id,
            "task_id": task_id,
            "scheduled_duration_min": 60,
            "actual_duration_min": actual,
            "completed": True,
            "completion_timestamp": "2026-06-09T19:30:00-07:00",
            "user_reschedule_count": 0,
            "data_quality": "complete",
        }
    )


def _model(*, ratio_min: int = 84, count: int = 6) -> PooledDurationModel:
    """An artifact with one dense practice bucket (evening/tue/medium/baseline)."""
    events = [_event(f"tel_{i}", "t1", ratio_min) for i in range(count)]
    user = PooledTrainingInput(
        user_id="user_a",
        events=events,
        task_categories={"t1": TaskCategory.PRACTICE},
        task_cognitive_loads={"t1": 4},
        experience_level=ExperienceLevel.BEGINNER,
        timezone="America/Los_Angeles",
        recent_completion_rate=0.7,
    )
    return train_pooled_model(
        [user], consented_user_ids={"user_a"}, model_version="v", trained_at=T0
    )


def _per_user(multiplier: float = 1.05) -> UserDurationMultipliers:
    """Defaults to 1.05 — inside the ``baseline`` multiplier band, matching
    the band the test artifact was trained under (no historical multiplier
    → 1.0 → baseline). A diverged per-user value (e.g. 1.2 → ``slower``)
    queries a different band and legitimately misses these buckets."""
    return UserDurationMultipliers(
        user_id="user_x",
        computed_at=T0,
        multipliers=[
            CategoryMultiplier(
                category=TaskCategory.PRACTICE,
                multiplier=multiplier,
                sample_size=7,
                observed_ratio=multiplier,
            )
        ],
    )


def _resolve(**overrides: object):
    kwargs: dict[str, object] = {
        "experience_level": ExperienceLevel.BEGINNER,
        "recent_completion_rate": 0.7,
        "per_user": _per_user(),
        "model": _model(),
        "pooled_denial_reason": None,
    }
    kwargs.update(overrides)
    return resolve_duration_multiplier(TaskCategory.PRACTICE, **kwargs)  # type: ignore[arg-type]


def test_pooled_hit_wins_and_names_source() -> None:
    model = _model()
    resolution = _resolve()
    assert resolution.source is DurationSource.POOLED
    assert resolution.multiplier == model.buckets[0].multiplier
    assert resolution.fallback_reasons == ()
    assert resolution.debug["source"] == "pooled"
    assert resolution.debug["matched_bucket_count"] == 1
    assert resolution.debug["combined_weighted_sample"] == 6.0


def test_sparse_bucket_falls_back_to_per_user() -> None:
    sparse_model = _model(count=3)  # weighted sample 3.0 < floor 5.0
    resolution = _resolve(model=sparse_model)
    assert resolution.source is DurationSource.PER_USER_CATEGORY
    assert resolution.multiplier == 1.05
    assert resolution.fallback_reasons == (ReasonCode.POOLED_BUCKET_SPARSE,)


def test_no_matching_bucket_falls_back() -> None:
    resolution = _resolve(experience_level=ExperienceLevel.ADVANCED)
    assert resolution.source is DurationSource.PER_USER_CATEGORY
    assert resolution.fallback_reasons == (ReasonCode.POOLED_BUCKET_SPARSE,)
    assert resolution.debug["matched_bucket_count"] == 0


def test_artifact_missing_falls_back_with_typed_reason() -> None:
    resolution = _resolve(model=None)
    assert resolution.source is DurationSource.PER_USER_CATEGORY
    assert resolution.fallback_reasons == (ReasonCode.POOLED_MODEL_UNAVAILABLE,)


def test_artifact_invalid_is_rejected_at_validation() -> None:
    """A tampered artifact fails contract validation; the composition root
    then serves with ``model=None`` (POOLED_MODEL_UNAVAILABLE)."""
    payload = _model().model_dump(mode="json")
    payload["content_hash"] = "sha256:" + "0" * 64
    with pytest.raises(ValidationError, match="content_hash does not match"):
        PooledDurationModel.model_validate(payload)


def test_opt_out_at_serving_time_falls_back() -> None:
    resolution = _resolve(pooled_denial_reason=ReasonCode.CONSENT_REVOKED)
    assert resolution.source is DurationSource.PER_USER_CATEGORY
    assert resolution.fallback_reasons == (ReasonCode.CONSENT_REVOKED,)


def test_full_chain_bottoms_out_at_heuristic_baseline() -> None:
    resolution = _resolve(model=None, per_user=None)
    assert resolution.source is DurationSource.HEURISTIC_BASELINE
    assert resolution.multiplier == 1.0
    assert resolution.fallback_reasons == (ReasonCode.POOLED_MODEL_UNAVAILABLE,)


def test_serving_floor_is_configurable() -> None:
    sparse_model = _model(count=3)
    resolution = _resolve(
        model=sparse_model, config=PooledServingConfig(serving_floor=2.0)
    )
    assert resolution.source is DurationSource.POOLED


def _plan() -> TaskPlan:
    return TaskPlan.model_validate(
        {
            "plan_version": "plan_v1",
            "tasks": [
                {
                    "task_id": "t_practice",
                    "module_id": "dp",
                    "title": "Practice set",
                    "category": "practice",
                    "estimated_duration_min": 60,
                    "cognitive_load": 4,
                    "dependencies": [],
                    "splittable": True,
                    "required_focus_level": "deep",
                },
                {
                    "task_id": "t_review",
                    "module_id": "dp",
                    "title": "Review notes",
                    "category": "review",
                    "estimated_duration_min": 30,
                    "cognitive_load": 2,
                    "dependencies": [],
                    "splittable": True,
                    "required_focus_level": "light",
                },
            ],
        }
    )


def test_plan_application_creates_new_version_only() -> None:
    plan = _plan()
    model = _model()
    effective, resolutions = resolve_effective_multipliers(
        [t.category for t in plan.tasks],
        user_id="user_x",
        computed_at=T0,
        experience_level=ExperienceLevel.BEGINNER,
        recent_completion_rate=0.7,
        per_user=_per_user(),
        model=model,
    )
    result = apply_duration_calibration(plan, effective, to_plan_version="plan_v2")
    assert result.plan.plan_version == "plan_v2"
    # The pooled multiplier (1.4 — uniform ratios) scaled the practice task.
    practice = next(t for t in result.plan.tasks if t.task_id == "t_practice")
    assert practice.estimated_duration_min == 84
    # Review had no pooled bucket and no per-user entry: untouched (1.0).
    review = next(t for t in result.plan.tasks if t.task_id == "t_review")
    assert review.estimated_duration_min == 30
    # The input plan was never mutated (active plan stays intact).
    assert plan.plan_version == "plan_v1"
    assert plan.tasks[0].estimated_duration_min == 60
    # Every category got an explainable resolution.
    sources = {r.category: r.source for r in resolutions}
    assert sources[TaskCategory.PRACTICE] is DurationSource.POOLED
    assert sources[TaskCategory.REVIEW] is DurationSource.HEURISTIC_BASELINE


def test_plan_application_per_user_tier_preserves_audit_fields() -> None:
    plan = _plan()
    effective, _ = resolve_effective_multipliers(
        [t.category for t in plan.tasks],
        user_id="user_x",
        computed_at=T0,
        experience_level=ExperienceLevel.BEGINNER,
        recent_completion_rate=0.7,
        per_user=_per_user(1.2),
        model=None,  # pooled unavailable → per-user tier
    )
    entry = next(
        m for m in effective.multipliers if m.category is TaskCategory.PRACTICE
    )
    # The Phase 2 entry is carried through verbatim (sample size, ratio).
    assert entry.multiplier == 1.2
    assert entry.sample_size == 7


def test_resolution_is_deterministic() -> None:
    a = _resolve()
    b = _resolve()
    assert a == b
