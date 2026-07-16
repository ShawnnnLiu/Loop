"""Tests for the ``show_placement_quality`` operator CLI.

Read-only by construction: the tool loads a serialized ``SchedulerInput``,
runs the pure scheduler, and prints the schedule-level scoring breakdown —
no store, no clock, no journal. Fixtures come from the shared
placement-quality corpus (``tests/fixtures/placement_quality/``).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agentic_calendar.tools.show_placement_quality import main

CORPUS_DIR = Path(__file__).parents[1] / "fixtures" / "placement_quality"
CORPUS_FILES = sorted(CORPUS_DIR.glob("*.json"))
ACCEPTANCE = CORPUS_DIR / "five_tasks_three_days.json"


def test_human_output_renders_the_breakdown(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = main([str(ACCEPTANCE)])
    out = capsys.readouterr().out
    assert code == 0
    assert "schedule_status: success" in out
    assert "per-day minutes:" in out
    assert "band histogram (placed starts):" in out
    assert "daily_balance_total" in out
    assert "total_cost:" in out
    assert "heuristic priors" in out


def test_json_output_carries_the_full_breakdown(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = main([str(ACCEPTANCE), "--json"])
    assert code == 0
    document = json.loads(capsys.readouterr().out)
    assert document["schedule_status"] == "success"
    breakdown = document["breakdown"]
    # The acceptance spread: 120/120/60 across the three free days.
    assert breakdown["per_day_minutes"] == {
        "2026-05-04": 120,
        "2026-05-05": 120,
        "2026-05-06": 60,
    }
    assert breakdown["scheduled_count"] == 5
    assert breakdown["unscheduled_count"] == 0
    for key in (
        "daily_balance_total",
        "back_to_back_total",
        "fragmentation_total",
        "deep_window_conservation_total",
        "evening_preference_total",
        "weekend_long_block_total",
        "total_cost",
        "target_daily_min",
        "band_histogram",
    ):
        assert key in breakdown


@pytest.mark.parametrize("path", CORPUS_FILES, ids=[p.stem for p in CORPUS_FILES])
def test_cli_succeeds_on_every_corpus_fixture(
    path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main([str(path), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["fixture"] == str(path)


def test_missing_fixture_is_a_typed_failure(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main([str(tmp_path / "nope.json")])
    captured = capsys.readouterr()
    assert code == 1
    assert captured.err.startswith("error:")
    assert captured.out == ""


def test_invalid_fixture_is_a_typed_failure(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text('{"run_id": "x"}', encoding="utf-8")
    code = main([str(bad)])
    captured = capsys.readouterr()
    assert code == 1
    assert captured.err.startswith("error:")
