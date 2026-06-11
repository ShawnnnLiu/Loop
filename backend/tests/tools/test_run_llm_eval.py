"""Tests for the ``run_llm_eval`` operator CLI (offline, deterministic)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agentic_calendar.tools.run_llm_eval import main

BACKEND_ROOT = Path(__file__).resolve().parents[2]
EVAL_SET = str(BACKEND_ROOT / "evalsets" / "eval_set_v1.json")
BASELINE = str(BACKEND_ROOT / "evalsets" / "recordings" / "fixture_baseline.json")
IMPROVED = str(BACKEND_ROOT / "evalsets" / "recordings" / "fixture_improved.json")


def test_baseline_reports_breach(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["--eval-set", EVAL_SET, "--recording", BASELINE])
    out = capsys.readouterr().out
    assert rc == 0  # breaches are reported, not turned into a failing build
    assert "THRESHOLD BREACH: post_repair_invalid_rate" in out
    assert "prove the harness, not live model quality" in out


def test_improved_satisfies_thresholds(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["--eval-set", EVAL_SET, "--recording", IMPROVED])
    out = capsys.readouterr().out
    assert rc == 0
    assert "All thresholds satisfied." in out


def test_out_writes_deterministic_report(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out_a = tmp_path / "a.json"
    out_b = tmp_path / "b.json"
    assert main(["--eval-set", EVAL_SET, "--recording", BASELINE, "--out", str(out_a)]) == 0
    assert main(["--eval-set", EVAL_SET, "--recording", BASELINE, "--out", str(out_b)]) == 0
    capsys.readouterr()
    assert out_a.read_text(encoding="utf-8") == out_b.read_text(encoding="utf-8")
    report = json.loads(out_a.read_text(encoding="utf-8"))
    assert report["eval_set_version"] == "v1"
    assert report["overall"]["cases"] == 6


def test_compare_prints_before_after(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    baseline_report = tmp_path / "baseline.json"
    assert (
        main(
            ["--eval-set", EVAL_SET, "--recording", BASELINE, "--out", str(baseline_report)]
        )
        == 0
    )
    capsys.readouterr()
    rc = main(
        ["--eval-set", EVAL_SET, "--recording", IMPROVED, "--compare", str(baseline_report)]
    )
    out = capsys.readouterr().out
    assert rc == 0
    assert "Before/after (eval set v1)" in out
    assert "overall schema_validity_rate: 0.6667 -> 1.0000 (delta +0.3333)" in out


def test_calls_aggregates_printed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    calls = [
        {
            "llm_call_log_id": "l1",
            "run_id": "run_cli",
            "node": "planner",
            "prompt_version": "p",
            "model_name": "m",
            "attempt": 0,
            "input_tokens": 6000,
            "output_tokens": 7000,
            "cost_estimate_usd": 0.005,
            "latency_ms": 9000,
            "validation_outcome": "pass",
            "created_at": "2026-06-10T14:05:00-07:00",
        }
    ]
    calls_path = tmp_path / "calls.json"
    calls_path.write_text(json.dumps(calls), encoding="utf-8")
    rc = main(
        ["--eval-set", EVAL_SET, "--recording", BASELINE, "--calls", str(calls_path)]
    )
    out = capsys.readouterr().out
    assert rc == 0
    assert "call aggregates (from llm_call_log records)" in out
    assert "calls=1 in_tok=6000 out_tok=7000" in out


def test_missing_file_is_error(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["--eval-set", EVAL_SET, "--recording", "/nonexistent/recording.json"])
    captured = capsys.readouterr()
    assert rc == 1
    assert "error:" in captured.err


def test_recording_case_mismatch_is_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bad = {"prompt_version": "p", "model_name": "m", "outputs": {}}
    bad_path = tmp_path / "bad.json"
    bad_path.write_text(json.dumps(bad), encoding="utf-8")
    rc = main(["--eval-set", EVAL_SET, "--recording", str(bad_path)])
    captured = capsys.readouterr()
    assert rc == 1
    assert "no outputs for cases" in captured.err
