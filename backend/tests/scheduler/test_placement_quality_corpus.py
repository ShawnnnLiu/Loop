"""Placement-quality fixture corpus (``tests/fixtures/placement_quality/``).

The corpus is the project's before/after evidence surface, shared with the
``show_placement_quality`` operator CLI. "Before" is the all-weights-zero
config — argmin over ``(0, start)`` places each task at its earliest
feasible start, i.e. the pre-scoring first-fit policy (modulo the deep-gap
grid fix and the regret insertion order; see ``ZERO_WEIGHTS`` in
``_helpers``) — and "after" is the default weights; both are scored with
``score_schedule`` under the *default* weights so the totals are
comparable.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from agentic_calendar.scheduler import schedule
from agentic_calendar.scheduler.inputs import SchedulerInput
from agentic_calendar.scheduler.scoring import score_schedule
from tests.scheduler._helpers import ZERO_WEIGHTS

CORPUS_DIR = Path(__file__).parents[1] / "fixtures" / "placement_quality"
CORPUS_FILES = sorted(CORPUS_DIR.glob("*.json"))


def _load(path: Path) -> SchedulerInput:
    return SchedulerInput.model_validate_json(path.read_text(encoding="utf-8"))


def test_corpus_is_present() -> None:
    assert len(CORPUS_FILES) >= 4


@pytest.mark.parametrize("path", CORPUS_FILES, ids=[p.stem for p in CORPUS_FILES])
def test_corpus_fixture_schedules_deterministically(path: Path) -> None:
    inp = _load(path)
    first = schedule(inp)
    second = schedule(_load(path))
    assert first.model_dump_json() == second.model_dump_json()
    assert first.scheduled_tasks, "corpus scenarios are schedulable by design"


@pytest.mark.parametrize("path", CORPUS_FILES, ids=[p.stem for p in CORPUS_FILES])
def test_default_weights_beat_the_zero_weight_baseline(path: Path) -> None:
    """On every corpus scenario the scored placement improves the
    schedule-level objective over earliest-feasible-start placement, without
    scheduling fewer tasks (soft terms never eliminate feasibility)."""
    inp = _load(path)
    baseline_out = schedule(inp, scoring=ZERO_WEIGHTS)
    scored_out = schedule(inp)
    baseline = score_schedule(baseline_out, inp)
    scored = score_schedule(scored_out, inp)
    assert scored.total_cost < baseline.total_cost
    assert scored.scheduled_count >= baseline.scheduled_count


def test_acceptance_fixture_spreads_across_days() -> None:
    """Definition-of-done anchor: 5 x 60-min tasks over 3 free days spread
    120/120/60 under default weights instead of stacking 240/60."""
    inp = _load(CORPUS_DIR / "five_tasks_three_days.json")
    baseline = score_schedule(schedule(inp, scoring=ZERO_WEIGHTS), inp)
    scored = score_schedule(schedule(inp), inp)
    assert baseline.per_day_minutes == {"2026-05-04": 240, "2026-05-05": 60}
    assert scored.per_day_minutes == {
        "2026-05-04": 120,
        "2026-05-05": 120,
        "2026-05-06": 60,
    }
    assert (baseline.daily_balance_total, baseline.back_to_back_total) == (140, 45)
    assert (scored.daily_balance_total, scored.back_to_back_total) == (40, 0)


def test_evening_preference_fixture_lands_in_the_evening_band() -> None:
    inp = _load(CORPUS_DIR / "evening_preference_week.json")
    baseline = score_schedule(schedule(inp, scoring=ZERO_WEIGHTS), inp)
    scored = score_schedule(schedule(inp), inp)
    assert baseline.band_histogram == {"morning": 4}
    assert scored.band_histogram == {"evening": 4}


def test_fragmented_weekend_fixture_earns_the_long_block_bonus() -> None:
    inp = _load(CORPUS_DIR / "fragmented_weekend.json")
    baseline = score_schedule(schedule(inp, scoring=ZERO_WEIGHTS), inp)
    scored = score_schedule(schedule(inp), inp)
    assert baseline.weekend_long_block_total == 0
    assert scored.weekend_long_block_total == 90  # the 90-min project task
