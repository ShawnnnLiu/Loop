"""Tests for the ``trace_llm_calls`` operator CLI."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from agentic_calendar.tools.trace_llm_calls import main

#: Raw content a careless implementation might leak. The trace must never
#: show it — only its hash ever entered the record.
_RAW_PROMPT = "You are a study planner. The user's calendar shows Dentist at 3pm."
_RAW_RESPONSE = "Here is your plan: study Dynamic Programming after the dentist."


def _row(
    log_id: str,
    run_id: str,
    *,
    outcome: str = "pass",
    reason: str | None = None,
    **overrides: Any,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "llm_call_log_id": log_id,
        "run_id": run_id,
        "plan_version": "v1",
        "node": "planner",
        "prompt_version": "planner-v1-2026-06-10",
        "model_name": "claude-haiku-4-5",
        "attempt": 0,
        "sdk_retry": 0,
        "input_tokens": 6100,
        "output_tokens": 7800,
        "cost_estimate_usd": 0.0451,
        "latency_ms": 9400,
        "validation_outcome": outcome,
        "reason_code": reason,
        "cache_hit": False,
        "truncated": False,
        "refusal": False,
        "prompt_hash": hashlib.sha256(_RAW_PROMPT.encode()).hexdigest(),
        "response_hash": hashlib.sha256(_RAW_RESPONSE.encode()).hexdigest(),
        "created_at": "2026-06-10T14:05:00-07:00",
    }
    row.update(overrides)
    return row


@pytest.fixture
def calls_file(tmp_path: Path) -> Path:
    rows = [
        _row("l1", "run_a"),
        _row(
            "l2",
            "run_a",
            outcome="fail",
            reason="LLM_SCHEMA_REJECTED",
            attempt=1,
            truncated=True,
        ),
        _row("l3", "run_b", node="strategist", prompt_version="strategist-v1-2026-06-10"),
    ]
    path = tmp_path / "calls.json"
    path.write_text(json.dumps(rows), encoding="utf-8")
    return path


def test_trace_renders_run_in_order(
    calls_file: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = main(["--calls", str(calls_file), "--run-id", "run_a"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "LLM call trace for run_id=run_a (2 calls)" in out
    assert out.index("attempt=0") < out.index("attempt=1")
    assert "planner-v1-2026-06-10" in out
    assert "tokens=6100/7800" in out
    assert "latency=9400ms" in out
    assert "reason=LLM_SCHEMA_REJECTED" in out
    assert "truncated" in out
    assert "failed_calls=1" in out
    assert "estimates" in out  # axiom 09 disclosure


def test_trace_contains_no_raw_content(
    calls_file: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Axiom 22 privacy: no raw calendar titles, prompts, or responses."""
    rc = main(["--calls", str(calls_file), "--run-id", "run_a"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "Dentist" not in out
    assert _RAW_PROMPT not in out
    assert _RAW_RESPONSE not in out


def test_without_run_id_lists_runs(
    calls_file: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = main(["--calls", str(calls_file)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "2 run(s)" in out
    assert "run_a  (2 calls)" in out
    assert "run_b  (1 calls)" in out


def test_unknown_run_id_is_error(
    calls_file: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = main(["--calls", str(calls_file), "--run-id", "run_missing"])
    captured = capsys.readouterr()
    assert rc == 1
    assert "no calls recorded" in captured.err


def test_invalid_row_is_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps([{"llm_call_log_id": "x"}]), encoding="utf-8")
    rc = main(["--calls", str(bad), "--run-id", "run_a"])
    captured = capsys.readouterr()
    assert rc == 1
    assert "error:" in captured.err


def test_non_list_file_is_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"not": "a list"}), encoding="utf-8")
    rc = main(["--calls", str(bad), "--run-id", "run_a"])
    captured = capsys.readouterr()
    assert rc == 1
    assert "must contain a JSON list" in captured.err
