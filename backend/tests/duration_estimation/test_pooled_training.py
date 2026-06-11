"""Tests for ``train_pooled_model``: replay, shrinkage math, consent gating.

The phase plan's training-side guarantees:

* same telemetry → same artifact ``content_hash`` (replay determinism);
* shrinkage blends bucket medians toward the global prior by sample size,
  with exact arithmetic pinned at boundary sample sizes;
* a non-consented user's events are provably absent from a rebuilt artifact
  (the opt-out-removes-from-training test).
"""

from __future__ import annotations

from datetime import UTC, datetime

from agentic_calendar.contracts.common_types import ExperienceLevel, TaskCategory
from agentic_calendar.contracts.pooled_duration_model import (
    CompletionRateBand,
    DayOfWeek,
    MultiplierBand,
    TimeOfDayBand,
)
from agentic_calendar.contracts.telemetry import TelemetryEvent
from agentic_calendar.contracts.user_duration_multipliers import (
    CategoryMultiplier,
    UserDurationMultipliers,
)
from agentic_calendar.duration_estimation.pooled import (
    PooledTrainingConfig,
    PooledTrainingInput,
    derive_completion_rate_band,
    derive_multiplier_band,
    derive_time_of_day_band,
    train_pooled_model,
)

T0 = datetime(2026, 6, 10, 16, 0, tzinfo=UTC)


def _event(
    event_id: str,
    task_id: str,
    actual: int,
    *,
    scheduled: int = 60,
    ts: str = "2026-06-09T19:30:00-07:00",
    data_quality: str = "complete",
    completed: bool = True,
) -> TelemetryEvent:
    payload: dict[str, object] = {
        "telemetry_event_id": event_id,
        "task_id": task_id,
        "scheduled_duration_min": scheduled,
        "completed": completed,
        "user_reschedule_count": 0,
        "data_quality": data_quality,
    }
    if completed:
        payload["actual_duration_min"] = actual
        payload["completion_timestamp"] = ts
    return TelemetryEvent.model_validate(payload)


def _input(
    user_id: str,
    events: list[TelemetryEvent],
    *,
    completion_rate: float = 0.7,
    multipliers: UserDurationMultipliers | None = None,
) -> PooledTrainingInput:
    return PooledTrainingInput(
        user_id=user_id,
        events=events,
        task_categories={e.task_id: TaskCategory.PRACTICE for e in events},
        task_cognitive_loads={e.task_id: 4 for e in events},
        experience_level=ExperienceLevel.BEGINNER,
        timezone="America/Los_Angeles",
        recent_completion_rate=completion_rate,
        historical_multipliers=multipliers,
    )


def test_replay_same_inputs_same_hash() -> None:
    events = [_event(f"tel_{i}", "t1", 84) for i in range(6)]
    a = train_pooled_model(
        [_input("user_a", events)],
        consented_user_ids={"user_a"},
        model_version="v-a",
        trained_at=T0,
    )
    b = train_pooled_model(
        [_input("user_a", events)],
        consented_user_ids={"user_a"},
        model_version="v-b",  # different label, different clock
        trained_at=datetime(2026, 7, 1, tzinfo=UTC),
    )
    assert a.content_hash == b.content_hash
    assert a.model_dump(exclude={"model_version", "trained_at"}) == b.model_dump(
        exclude={"model_version", "trained_at"}
    )


def test_non_consented_users_events_are_absent() -> None:
    """The opt-out test: user_b's events affect nothing — not buckets, not
    the prior — so the artifact equals a rebuild without user_b entirely."""
    events_a = [_event(f"a_{i}", "t1", 84) for i in range(6)]
    events_b = [_event(f"b_{i}", "t2", 30) for i in range(6)]  # very different ratios
    with_b_present_but_unconsented = train_pooled_model(
        [_input("user_a", events_a), _input("user_b", events_b)],
        consented_user_ids={"user_a"},
        model_version="v",
        trained_at=T0,
    )
    without_b_at_all = train_pooled_model(
        [_input("user_a", events_a)],
        consented_user_ids={"user_a"},
        model_version="v",
        trained_at=T0,
    )
    assert with_b_present_but_unconsented.content_hash == without_b_at_all.content_hash


def test_consented_users_events_do_change_the_artifact() -> None:
    events_a = [_event(f"a_{i}", "t1", 84) for i in range(6)]
    events_b = [_event(f"b_{i}", "t2", 30) for i in range(6)]
    only_a = train_pooled_model(
        [_input("user_a", events_a)],
        consented_user_ids={"user_a"},
        model_version="v",
        trained_at=T0,
    )
    both = train_pooled_model(
        [_input("user_a", events_a), _input("user_b", events_b)],
        consented_user_ids={"user_a", "user_b"},
        model_version="v",
        trained_at=T0,
    )
    assert only_a.content_hash != both.content_hash


def test_shrinkage_math_exact() -> None:
    """One bucket, ratio 1.4 (n=6, all weight 1.0); prior is that same median
    so shrinkage is the identity: (6*1.4 + 5*1.4) / 11 = 1.4. With a second
    contrasting bucket the blend moves each toward the cross-bucket prior."""
    fast = [_event(f"f_{i}", "t_fast", 30) for i in range(6)]  # ratio 0.5
    slow = [_event(f"s_{i}", "t_slow", 84) for i in range(6)]  # ratio 1.4
    user = PooledTrainingInput(
        user_id="user_a",
        events=[*fast, *slow],
        task_categories={
            **{e.task_id: TaskCategory.CONCEPT_REVIEW for e in fast},
            **{e.task_id: TaskCategory.PRACTICE for e in slow},
        },
        task_cognitive_loads={e.task_id: 3 for e in [*fast, *slow]},
        experience_level=ExperienceLevel.INTERMEDIATE,
        timezone="America/Los_Angeles",
        recent_completion_rate=0.7,
    )
    model = train_pooled_model(
        [user], consented_user_ids={"user_a"}, model_version="v", trained_at=T0
    )
    # Global prior: weighted median over six 0.5s and six 1.4s = (0.5+1.4)/2.
    assert model.global_prior_multiplier == (0.5 + 1.4) / 2
    by_cat = {b.category: b for b in model.buckets}
    prior = model.global_prior_multiplier
    expected_slow = (6 * 1.4 + 5 * prior) / 11
    expected_fast = (6 * 0.5 + 5 * prior) / 11
    assert by_cat[TaskCategory.PRACTICE].multiplier == expected_slow
    assert by_cat[TaskCategory.CONCEPT_REVIEW].multiplier == expected_fast
    assert by_cat[TaskCategory.PRACTICE].observed_ratio == 1.4
    assert by_cat[TaskCategory.PRACTICE].sample_size == 6


def test_shrinkage_boundary_single_low_weight_event() -> None:
    """n -> 0 boundary: one manual_backfill event (weight 0.5) barely moves
    the bucket off the prior: (0.5*r + 5*prior) / 5.5."""
    strong = [_event(f"s_{i}", "t_strong", 60) for i in range(8)]  # ratio 1.0
    weak = [
        _event("w_0", "t_weak", 120, data_quality="manual_backfill")
    ]  # ratio 2.0, weight 0.5
    user = PooledTrainingInput(
        user_id="user_a",
        events=[*strong, *weak],
        task_categories={
            **{e.task_id: TaskCategory.PRACTICE for e in strong},
            "t_weak": TaskCategory.PROJECT,
        },
        task_cognitive_loads={**{e.task_id: 3 for e in strong}, "t_weak": 3},
        experience_level=ExperienceLevel.INTERMEDIATE,
        timezone="America/Los_Angeles",
        recent_completion_rate=0.7,
    )
    model = train_pooled_model(
        [user], consented_user_ids={"user_a"}, model_version="v", trained_at=T0
    )
    prior = model.global_prior_multiplier  # weighted median ≈ 1.0
    assert prior == 1.0
    weak_bucket = next(b for b in model.buckets if b.category is TaskCategory.PROJECT)
    assert weak_bucket.weighted_sample == 0.5
    assert weak_bucket.multiplier == (0.5 * 2.0 + 5.0 * 1.0) / 5.5


def test_multiplier_clamped_to_band() -> None:
    events = [_event(f"x_{i}", "t1", 300) for i in range(20)]  # ratio 5.0
    model = train_pooled_model(
        [_input("user_a", events)],
        consented_user_ids={"user_a"},
        model_version="v",
        trained_at=T0,
        config=PooledTrainingConfig(shrinkage_strength=0.0),
    )
    assert model.buckets[0].multiplier == 2.0  # clamped, not 5.0
    assert model.global_prior_multiplier == 2.0


def test_estimated_and_incomplete_events_excluded() -> None:
    real = [_event(f"r_{i}", "t1", 84) for i in range(6)]
    noise = [
        _event("n_0", "t1", 60, completed=False),
    ]
    with_noise = train_pooled_model(
        [_input("user_a", [*real, *noise])],
        consented_user_ids={"user_a"},
        model_version="v",
        trained_at=T0,
    )
    without_noise = train_pooled_model(
        [_input("user_a", real)],
        consented_user_ids={"user_a"},
        model_version="v",
        trained_at=T0,
    )
    assert with_noise.content_hash == without_noise.content_hash


def test_empty_inputs_yield_neutral_prior() -> None:
    model = train_pooled_model(
        [], consented_user_ids=set(), model_version="v", trained_at=T0
    )
    assert model.global_prior_multiplier == 1.0
    assert model.global_prior_weighted_sample == 0.0
    assert model.buckets == []


def test_feature_derivation_bands() -> None:
    assert derive_time_of_day_band(5).value == "morning"
    assert derive_time_of_day_band(11).value == "morning"
    assert derive_time_of_day_band(12).value == "afternoon"
    assert derive_time_of_day_band(16).value == "afternoon"
    assert derive_time_of_day_band(17).value == "evening"
    assert derive_time_of_day_band(21).value == "evening"
    assert derive_time_of_day_band(22).value == "night"
    assert derive_time_of_day_band(4).value == "night"
    assert derive_completion_rate_band(0.49).value == "low"
    assert derive_completion_rate_band(0.5).value == "medium"
    assert derive_completion_rate_band(0.79).value == "medium"
    assert derive_completion_rate_band(0.8).value == "high"
    assert derive_multiplier_band(0.89).value == "faster"
    assert derive_multiplier_band(0.9).value == "baseline"
    assert derive_multiplier_band(1.1).value == "baseline"
    assert derive_multiplier_band(1.11).value == "slower"


def test_bucket_features_reflect_user_context() -> None:
    multipliers = UserDurationMultipliers(
        user_id="user_a",
        computed_at=T0,
        multipliers=[
            CategoryMultiplier(
                category=TaskCategory.PRACTICE,
                multiplier=1.35,
                sample_size=8,
                observed_ratio=1.35,
            )
        ],
    )
    events = [_event(f"e_{i}", "t1", 84) for i in range(6)]  # Tue 19:30 PT
    model = train_pooled_model(
        [_input("user_a", events, completion_rate=0.4, multipliers=multipliers)],
        consented_user_ids={"user_a"},
        model_version="v",
        trained_at=T0,
    )
    bucket = model.buckets[0]
    assert bucket.time_of_day_band is TimeOfDayBand.EVENING
    assert bucket.day_of_week is DayOfWeek.TUE
    assert bucket.completion_rate_band is CompletionRateBand.LOW
    assert bucket.multiplier_band is MultiplierBand.SLOWER
