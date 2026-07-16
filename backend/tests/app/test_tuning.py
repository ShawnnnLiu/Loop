"""Tests for the tuning loader (``app/tuning.py``, Phase 9d).

Every assertion pins the axiom 07 invariants: no silent threshold changes
(every effective override journals exactly one entry), idempotent re-load
(the same file appends nothing twice), and deterministic replay (the journal
alone reproduces every effective value).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from agentic_calendar.app.threshold_log import InMemoryThresholdChangeLogStore
from agentic_calendar.app.tuning import (
    ABSENT_DATASET_REFERENCE,
    REVERSION_DATASET_REFERENCE,
    REVERSION_JUSTIFICATION,
    TUNABLE_SECTIONS,
    EffectiveTuning,
    TuningError,
    apply_tuning,
    load_tuning_file,
    replay_effective,
)
from agentic_calendar.common.clock import FrozenClock
from agentic_calendar.common.ids import DeterministicIdGenerator
from agentic_calendar.drift.thresholds import DEFAULT_DRIFT_THRESHOLDS
from agentic_calendar.duration_estimation.pooled import (
    DEFAULT_POOLED_SERVING_CONFIG,
    DEFAULT_POOLED_TRAINING_CONFIG,
)
from agentic_calendar.duration_estimation.power_user import (
    DEFAULT_ELIGIBILITY_CONFIG,
    DEFAULT_REFINEMENT_CONFIG,
)
from agentic_calendar.scheduler.scoring import DEFAULT_PLACEMENT_SCORING_CONFIG
from agentic_calendar.telemetry.calibration import DEFAULT_CALIBRATION_CONFIG

_T0 = datetime(2026, 6, 11, 12, 0, 0, tzinfo=UTC)

PROSE = {
    "justification": "Loosened after repeated false positives in dogfooding.",
    "dataset_reference": "telemetry through 2026-06-10",
}


def _apply(
    parsed: dict[str, object] | None,
    store: InMemoryThresholdChangeLogStore,
    ids: DeterministicIdGenerator | None = None,
) -> EffectiveTuning:
    """One ``apply_tuning`` pass. Multi-apply tests share ``ids`` because the
    journal is append-only and a reset counter would collide on ``thrchg_001``
    (production uses UUID-backed ids per environment)."""
    return apply_tuning(
        parsed=parsed,
        store=store,
        clock=FrozenClock(_T0),
        id_generator=ids if ids is not None else DeterministicIdGenerator(),
    )


# --------------------------------------------------------------------------- #
# defaults path (byte-identical acceptance)
# --------------------------------------------------------------------------- #


def test_no_file_returns_all_defaults_and_touches_nothing() -> None:
    """``parsed=None`` serves the exact default instances and appends nothing
    — running without a tuning file must be byte-identical to before."""
    store = InMemoryThresholdChangeLogStore()
    tuning = _apply(None, store)
    assert tuning.drift_thresholds == DEFAULT_DRIFT_THRESHOLDS
    assert tuning.calibration == DEFAULT_CALIBRATION_CONFIG
    assert tuning.pooled_training == DEFAULT_POOLED_TRAINING_CONFIG
    assert tuning.pooled_serving == DEFAULT_POOLED_SERVING_CONFIG
    assert tuning.power_user_eligibility == DEFAULT_ELIGIBILITY_CONFIG
    assert tuning.per_user_refinement == DEFAULT_REFINEMENT_CONFIG
    assert tuning.scheduler_placement == DEFAULT_PLACEMENT_SCORING_CONFIG
    assert store.list_all() == []


def test_empty_parsed_file_is_all_defaults() -> None:
    """A fully commented tuning.toml parses to ``{}`` — also all defaults."""
    store = InMemoryThresholdChangeLogStore()
    tuning = _apply({}, store)
    assert tuning.drift_thresholds == DEFAULT_DRIFT_THRESHOLDS
    assert store.list_all() == []


def test_shipped_example_file_is_all_defaults(tmp_path: Path) -> None:
    """The committed ``backend/tuning.toml`` has no active overrides."""
    parsed = load_tuning_file(Path(__file__).parents[2] / "tuning.toml")
    store = InMemoryThresholdChangeLogStore()
    tuning = _apply(parsed, store)
    assert tuning == _apply(None, InMemoryThresholdChangeLogStore())
    assert store.list_all() == []


# --------------------------------------------------------------------------- #
# journaling
# --------------------------------------------------------------------------- #


def test_override_journals_one_entry_with_default_prior() -> None:
    """First override of a field journals prior=default, new=override, plus
    the file's prose (axiom 07's seven required record parts)."""
    store = InMemoryThresholdChangeLogStore()
    tuning = _apply(
        {"drift_thresholds": {"duration_underestimate_ratio": 1.4}} | PROSE, store
    )
    assert tuning.drift_thresholds.duration_underestimate_ratio == 1.4
    # Untouched fields keep their defaults.
    assert tuning.drift_thresholds.duration_min_sample == 5
    entries = store.list_all()
    assert len(entries) == 1
    entry = entries[0]
    assert entry.config_section == "drift_thresholds"
    assert entry.threshold_field == "duration_underestimate_ratio"
    assert entry.prior_value == DEFAULT_DRIFT_THRESHOLDS.duration_underestimate_ratio
    assert entry.new_value == 1.4
    assert entry.effective_at == _T0
    assert entry.justification == PROSE["justification"]
    assert entry.dataset_reference == PROSE["dataset_reference"]


def test_reapplying_same_file_appends_nothing() -> None:
    """Idempotent re-load: every CLI invocation re-applies the file, so an
    unchanged override must not spam the journal."""
    store = InMemoryThresholdChangeLogStore()
    parsed = {"drift_thresholds": {"duration_underestimate_ratio": 1.4}} | PROSE
    first = _apply(parsed, store)
    second = _apply(parsed, store)
    assert first == second
    assert len(store.list_all()) == 1


def test_second_change_journals_prior_from_first_override() -> None:
    """History replay: the second entry's prior_value is the first override,
    never the default — the journal is a chain, not a diff against defaults."""
    store = InMemoryThresholdChangeLogStore()
    ids = DeterministicIdGenerator()
    _apply(
        {"drift_thresholds": {"duration_underestimate_ratio": 1.4}} | PROSE, store, ids
    )
    tuning = _apply(
        {"drift_thresholds": {"duration_underestimate_ratio": 1.5}} | PROSE, store, ids
    )
    assert tuning.drift_thresholds.duration_underestimate_ratio == 1.5
    entries = store.list_all()
    assert len(entries) == 2
    assert entries[1].prior_value == 1.4
    assert entries[1].new_value == 1.5


def test_int_field_override_and_float_coercion() -> None:
    """Int fields stay ints; an int given for a float field is stored and
    served as a float (TOML writers naturally write ``2`` for ``2.0``)."""
    store = InMemoryThresholdChangeLogStore()
    tuning = _apply(
        {
            "drift_thresholds": {"duration_min_sample": 4},
            "calibration": {"multiplier_max": 3},
        }
        | PROSE,
        store,
    )
    assert tuning.drift_thresholds.duration_min_sample == 4
    assert tuning.calibration.multiplier_max == 3.0
    assert isinstance(tuning.calibration.multiplier_max, float)
    by_field = {(e.config_section, e.threshold_field): e for e in store.list_all()}
    assert isinstance(
        by_field[("drift_thresholds", "duration_min_sample")].new_value, int
    )
    assert isinstance(by_field[("calibration", "multiplier_max")].new_value, float)


def test_scheduler_placement_weight_override_journals_and_serves() -> None:
    """The placement weights ride the same axiom-07 path as every section:
    an override serves through ``EffectiveTuning.scheduler_placement`` and
    journals exactly one entry."""
    store = InMemoryThresholdChangeLogStore()
    tuning = _apply(
        {"scheduler_placement": {"w_daily_balance": 5, "w_earliness": 2}} | PROSE,
        store,
    )
    assert tuning.scheduler_placement.w_daily_balance == 5
    assert tuning.scheduler_placement.w_earliness == 2
    # Untouched knobs keep their defaults.
    assert tuning.scheduler_placement.candidate_grid_min == (
        DEFAULT_PLACEMENT_SCORING_CONFIG.candidate_grid_min
    )
    by_field = {e.threshold_field: e for e in store.list_all()}
    assert set(by_field) == {"w_daily_balance", "w_earliness"}
    for entry in by_field.values():
        assert entry.config_section == "scheduler_placement"
    assert by_field["w_daily_balance"].prior_value == (
        DEFAULT_PLACEMENT_SCORING_CONFIG.w_daily_balance
    )
    assert by_field["w_daily_balance"].new_value == 5
    assert by_field["w_earliness"].prior_value == (
        DEFAULT_PLACEMENT_SCORING_CONFIG.w_earliness
    )
    assert by_field["w_earliness"].new_value == 2


def test_replay_effective_reproduces_history() -> None:
    """The journal alone deterministically reproduces every effective value.

    The second file keeps the ``serving_floor`` override — dropping it would
    journal a reversion (covered separately below)."""
    store = InMemoryThresholdChangeLogStore()
    ids = DeterministicIdGenerator()
    _apply(
        {
            "drift_thresholds": {"duration_underestimate_ratio": 1.4},
            "pooled_serving": {"serving_floor": 6.0},
        }
        | PROSE,
        store,
        ids,
    )
    _apply(
        {
            "drift_thresholds": {"duration_underestimate_ratio": 1.5},
            "pooled_serving": {"serving_floor": 6.0},
        }
        | PROSE,
        store,
        ids,
    )
    assert replay_effective(store) == {
        "drift_thresholds": {"duration_underestimate_ratio": 1.5},
        "pooled_serving": {"serving_floor": 6.0},
    }


# --------------------------------------------------------------------------- #
# reversions — removing an override is a journaled change too
# --------------------------------------------------------------------------- #


def test_removed_override_journals_reversion_back_to_default() -> None:
    """A file that no longer carries a journaled override journals exactly one
    reversion (prior=old override, new=default) and serves the default again.
    A file with no overrides carries no prose, so the constants fill in."""
    store = InMemoryThresholdChangeLogStore()
    ids = DeterministicIdGenerator()
    _apply(
        {"drift_thresholds": {"duration_underestimate_ratio": 1.4}} | PROSE, store, ids
    )
    tuning = _apply({}, store, ids)
    assert (
        tuning.drift_thresholds.duration_underestimate_ratio
        == DEFAULT_DRIFT_THRESHOLDS.duration_underestimate_ratio
    )
    entries = store.list_all()
    assert len(entries) == 2
    reversion = entries[1]
    assert reversion.config_section == "drift_thresholds"
    assert reversion.threshold_field == "duration_underestimate_ratio"
    assert reversion.prior_value == 1.4
    assert (
        reversion.new_value == DEFAULT_DRIFT_THRESHOLDS.duration_underestimate_ratio
    )
    assert reversion.justification == REVERSION_JUSTIFICATION
    assert reversion.dataset_reference == REVERSION_DATASET_REFERENCE
    # Idempotent: the replayed value now equals the default, so re-applying
    # the same override-free file appends nothing.
    again = _apply({}, store, ids)
    assert again == tuning
    assert len(store.list_all()) == 2


def test_absent_file_journals_reversion_and_serves_defaults() -> None:
    """``parsed=None`` after a journaled override is a reversion, not a
    silent fallback to the default — and the second None apply is a no-op."""
    store = InMemoryThresholdChangeLogStore()
    ids = DeterministicIdGenerator()
    _apply(
        {"drift_thresholds": {"duration_underestimate_ratio": 1.4}} | PROSE, store, ids
    )
    tuning = _apply(None, store, ids)
    assert tuning == _apply(None, InMemoryThresholdChangeLogStore())
    assert tuning.drift_thresholds == DEFAULT_DRIFT_THRESHOLDS
    entries = store.list_all()
    assert len(entries) == 2
    reversion = entries[1]
    assert reversion.prior_value == 1.4
    assert (
        reversion.new_value == DEFAULT_DRIFT_THRESHOLDS.duration_underestimate_ratio
    )
    assert reversion.justification == REVERSION_JUSTIFICATION
    assert reversion.dataset_reference == ABSENT_DATASET_REFERENCE
    second = _apply(None, store, ids)
    assert second == tuning
    assert len(store.list_all()) == 2


def test_change_and_reversion_in_one_apply_use_file_prose() -> None:
    """A file that changes one journaled override and drops another journals
    both — the change and the reversion — with the file's own prose."""
    store = InMemoryThresholdChangeLogStore()
    ids = DeterministicIdGenerator()
    _apply(
        {
            "drift_thresholds": {"duration_underestimate_ratio": 1.4},
            "pooled_serving": {"serving_floor": 6.0},
        }
        | PROSE,
        store,
        ids,
    )
    prose_b = {
        "justification": "Tightened the ratio; floor override retired.",
        "dataset_reference": "telemetry through 2026-06-11",
    }
    tuning = _apply(
        {"drift_thresholds": {"duration_underestimate_ratio": 1.5}} | prose_b,
        store,
        ids,
    )
    assert tuning.drift_thresholds.duration_underestimate_ratio == 1.5
    assert (
        tuning.pooled_serving.serving_floor
        == DEFAULT_POOLED_SERVING_CONFIG.serving_floor
    )
    by_field = {(e.config_section, e.threshold_field): e for e in store.list_all()[2:]}
    assert len(by_field) == 2
    change = by_field[("drift_thresholds", "duration_underestimate_ratio")]
    assert (change.prior_value, change.new_value) == (1.4, 1.5)
    reversion = by_field[("pooled_serving", "serving_floor")]
    assert reversion.prior_value == 6.0
    assert reversion.new_value == DEFAULT_POOLED_SERVING_CONFIG.serving_floor
    for entry in (change, reversion):
        assert entry.justification == prose_b["justification"]
        assert entry.dataset_reference == prose_b["dataset_reference"]
    # Replay agrees with serving on both the changed and the reverted field.
    assert replay_effective(store)["pooled_serving"]["serving_floor"] == (
        DEFAULT_POOLED_SERVING_CONFIG.serving_floor
    )


# --------------------------------------------------------------------------- #
# typed rejections — every error names the offender
# --------------------------------------------------------------------------- #


def test_unknown_section_rejected() -> None:
    store = InMemoryThresholdChangeLogStore()
    with pytest.raises(TuningError, match="unknown tuning section 'scheduler'"):
        _apply({"scheduler": {"horizon_days": 7}} | PROSE, store)
    assert store.list_all() == []


def test_unknown_field_rejected() -> None:
    store = InMemoryThresholdChangeLogStore()
    with pytest.raises(
        TuningError, match="unknown field 'no_such_knob' in tuning section"
    ):
        _apply({"drift_thresholds": {"no_such_knob": 1}} | PROSE, store)


def test_non_scalar_field_rejected() -> None:
    """``calibration.quality_weights`` is a mapping — not a scalar tunable."""
    store = InMemoryThresholdChangeLogStore()
    with pytest.raises(
        TuningError, match=r"calibration\.quality_weights is not a scalar tunable"
    ):
        _apply({"calibration": {"quality_weights": {"complete": 1.0}}} | PROSE, store)


def test_string_value_rejected() -> None:
    store = InMemoryThresholdChangeLogStore()
    with pytest.raises(
        TuningError,
        match=r"drift_thresholds\.duration_underestimate_ratio expects float, got str",
    ):
        _apply(
            {"drift_thresholds": {"duration_underestimate_ratio": "1.4"}} | PROSE,
            store,
        )


def test_bool_value_rejected() -> None:
    """``True == 1`` must not slip through as an int override."""
    store = InMemoryThresholdChangeLogStore()
    with pytest.raises(
        TuningError, match=r"drift_thresholds\.duration_min_sample expects int, got bool"
    ):
        _apply({"drift_thresholds": {"duration_min_sample": True}} | PROSE, store)


def test_int_field_given_float_rejected() -> None:
    store = InMemoryThresholdChangeLogStore()
    with pytest.raises(
        TuningError, match=r"drift_thresholds\.duration_min_sample expects int, got float"
    ):
        _apply({"drift_thresholds": {"duration_min_sample": 4.0}} | PROSE, store)


def test_missing_justification_rejected() -> None:
    """Overrides without prose are unauditable — axiom 07 requires both."""
    store = InMemoryThresholdChangeLogStore()
    with pytest.raises(TuningError, match="require a top-level justification"):
        _apply(
            {
                "drift_thresholds": {"duration_underestimate_ratio": 1.4},
                "dataset_reference": "manual prior",
            },
            store,
        )
    with pytest.raises(TuningError, match="require a top-level dataset_reference"):
        _apply(
            {
                "drift_thresholds": {"duration_underestimate_ratio": 1.4},
                "justification": "because",
            },
            store,
        )
    assert store.list_all() == []


def test_registry_covers_exactly_the_effective_tuning_fields() -> None:
    """Registry section names and ``EffectiveTuning`` fields must stay in
    lockstep — ``apply_tuning`` builds one from the other by name."""
    from dataclasses import fields

    assert set(TUNABLE_SECTIONS) == {f.name for f in fields(EffectiveTuning)}
