"""Tests for the ``show_thresholds`` operator CLI (Phase 9d).

The CLI is read-only by contract: it renders defaults, journal replay, and an
optional tuning-file preview, and must never append a journal entry itself —
journaling is ``build_environment``'s job (axiom 07 "Threshold Change Log").
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agentic_calendar.app.environment import (
    LlmNodeBundle,
    NodeDependencies,
    build_environment,
)
from agentic_calendar.app.threshold_log import SqliteThresholdChangeLogStore
from agentic_calendar.common.sqlite import SqliteDatabase
from agentic_calendar.llm_nodes.planner import FixturePlanner
from agentic_calendar.llm_nodes.reflection_summary import DeterministicReflectionSummary
from agentic_calendar.llm_nodes.resume_intake import FixtureResumeIntake
from agentic_calendar.llm_nodes.strategist import FixtureStrategist
from agentic_calendar.llm_nodes.user_facing_explanation import (
    DeterministicUserFacingExplanation,
)
from agentic_calendar.tools.llm_smoke import sample_fixture_inputs
from agentic_calendar.tools.show_thresholds import main

TUNING_TOML = (
    'justification = "Loosened after repeated false positives in dogfooding."\n'
    'dataset_reference = "telemetry through 2026-06-10"\n'
    "[drift_thresholds]\n"
    "duration_underestimate_ratio = 1.4\n"
)


def _nodes_factory(deps: NodeDependencies) -> LlmNodeBundle:
    """Smoke-sample fixture nodes: these tests never run a propose cycle."""
    del deps
    profile, syllabus, plan = sample_fixture_inputs()
    return LlmNodeBundle(
        strategist=FixtureStrategist({profile.target_role: syllabus}),
        planner=FixturePlanner({syllabus.syllabus_version: plan}),
        reflection=DeterministicReflectionSummary(),
        explanation=DeterministicUserFacingExplanation(),
        # These tests never extract; a minimal alias mapping satisfies the node.
        resume_intake=FixtureResumeIntake(taxonomy_aliases={"python": "Python"}),
    )


def _journal_override(tmp_path: Path) -> Path:
    """Apply a tuning override through the composition root (the supported
    mutation path), returning the SQLite db path that now holds one entry."""
    db_path = tmp_path / "dogfood.db"
    tuning_file = tmp_path / "tuning.toml"
    tuning_file.write_text(TUNING_TOML, encoding="utf-8")
    env = build_environment(
        nodes_factory=_nodes_factory, db_path=db_path, tuning_path=tuning_file
    )
    assert env.tuning.drift_thresholds.duration_underestimate_ratio == 1.4
    assert env.db is not None
    env.db.close()
    return db_path


def _entry_count(db_path: Path) -> int:
    db = SqliteDatabase(db_path)
    count = len(SqliteThresholdChangeLogStore(db).list_all())
    db.close()
    return count


def test_empty_db_prints_all_defaults(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """With no journal and no file, every field renders its default."""
    code = main(["--db", str(tmp_path / "empty.db")])
    out = capsys.readouterr().out
    assert code == 0
    assert "[drift_thresholds]" in out
    assert "duration_underestimate_ratio = 1.3 (default)" in out
    assert "[pooled_serving]" in out
    assert "serving_floor = 5.0 (default)" in out
    assert "history (0 entries):" in out
    assert "heuristic priors" in out


def test_journaled_override_shows_overridden_with_history(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """After the composition root applied an override, the CLI replays it
    from the journal alone (no --tuning needed) and prints the history line."""
    db_path = _journal_override(tmp_path)
    code = main(["--db", str(db_path)])
    out = capsys.readouterr().out
    assert code == 0
    assert "duration_underestimate_ratio = 1.4 (overridden)" in out
    assert "history (1 entries):" in out
    assert "drift_thresholds.duration_underestimate_ratio  1.3 -> 1.4" in out
    assert "justification: Loosened after repeated false positives" in out
    assert "dataset_reference: telemetry through 2026-06-10" in out
    # Untouched fields stay marked default.
    assert "duration_min_sample = 5 (default)" in out


def test_tuning_file_preview_marks_overridden_without_journaling(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A --tuning preview shows the file's values, but the journal stays
    empty — only the loader's mutating path may append (read-only proof)."""
    db_path = tmp_path / "empty.db"
    tuning_file = tmp_path / "tuning.toml"
    tuning_file.write_text(TUNING_TOML, encoding="utf-8")
    code = main(["--db", str(db_path), "--tuning", str(tuning_file)])
    out = capsys.readouterr().out
    assert code == 0
    assert "duration_underestimate_ratio = 1.4 (overridden)" in out
    assert "history (0 entries):" in out
    assert _entry_count(db_path) == 0


def test_tuning_preview_with_removed_override_shows_default_without_journaling(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A --tuning file that no longer carries a journaled override previews
    that field as default — applying the file would journal a reversion — but
    the read-only CLI itself appends nothing."""
    db_path = _journal_override(tmp_path)
    tuning_file = tmp_path / "tuning-removed.toml"
    tuning_file.write_text("# override retired\n", encoding="utf-8")
    code = main(["--db", str(db_path), "--tuning", str(tuning_file)])
    out = capsys.readouterr().out
    assert code == 0
    assert "duration_underestimate_ratio = 1.3 (default)" in out
    # The journal still holds only the original override entry.
    assert "history (1 entries):" in out
    assert _entry_count(db_path) == 1


def test_json_output_parses_and_appends_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """--json emits one parseable document; the run appends no entries."""
    db_path = _journal_override(tmp_path)
    before = _entry_count(db_path)
    code = main(["--db", str(db_path), "--json"])
    out = capsys.readouterr().out
    assert code == 0
    payload = json.loads(out)
    field = payload["sections"]["drift_thresholds"]["duration_underestimate_ratio"]
    assert field == {"value": 1.4, "status": "overridden"}
    assert payload["sections"]["calibration"]["multiplier_max"]["status"] == "default"
    assert len(payload["history"]) == 1
    entry = payload["history"][0]
    assert entry["config_section"] == "drift_thresholds"
    assert entry["prior_value"] == 1.3
    assert entry["new_value"] == 1.4
    assert _entry_count(db_path) == before


def test_invalid_tuning_file_fails_with_typed_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A bad preview file is rejected loudly, not rendered partially."""
    tuning_file = tmp_path / "tuning.toml"
    tuning_file.write_text("[scheduler]\nhorizon_days = 7\n", encoding="utf-8")
    code = main(["--db", str(tmp_path / "empty.db"), "--tuning", str(tuning_file)])
    captured = capsys.readouterr()
    assert code == 1
    assert "unknown tuning section 'scheduler'" in captured.err
