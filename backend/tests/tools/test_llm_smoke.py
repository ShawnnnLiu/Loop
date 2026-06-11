"""Tests for the ``llm_smoke`` operator CLI — every safeguard, zero network."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from agentic_calendar.llm_nodes.anthropic_adapter import TransportResult
from agentic_calendar.tools.llm_smoke import MAX_LIVE_CALLS, main

_SYLLABUS_OUT: dict[str, Any] = {
    "syllabus_version": "syl_live",
    "goal_summary": "Prepare for backend SWE interviews.",
    "modules": [
        {
            "module_id": "dp",
            "title": "Dynamic Programming",
            "priority": "high",
            "reason": "Listed weakness.",
            "target_outcomes": ["Recognize DP state definitions"],
            "estimated_total_min": 720,
            "difficulty": 5,
            "source_claim_ids": ["claim_012"],
        }
    ],
}

_PLAN_OUT: dict[str, Any] = {
    "plan_version": "plan_live",
    "tasks": [
        {
            "task_id": "dp_001",
            "module_id": "dp",
            "title": "Review DP state definitions",
            "dependencies": [],
            "estimated_duration_min": 60,
            "cognitive_load": 4,
            "category": "concept_review",
            "required_focus_level": "deep",
            "splittable": False,
        }
    ],
}

_REFLECTION_OUT: dict[str, Any] = {
    "summary": "Practice tasks are taking longer than planned.",
    "detail": ["Their time estimates will be increased."],
}

_EXPLANATION_OUT: dict[str, Any] = {"summary": "Plan looks good.", "detail": []}


class ScriptedTransport:
    """Returns canned results in order; never touches the network."""

    def __init__(self, payloads: list[dict[str, Any] | None]) -> None:
        self._payloads = list(payloads)
        self.calls = 0

    def complete(self, **kwargs: Any) -> TransportResult:
        self.calls += 1
        payload = self._payloads.pop(0) if self._payloads else None
        return TransportResult(
            payload=payload,
            raw_text="RAW_MARKER " + json.dumps(payload),
            stop_reason="end_turn",
            input_tokens=1000,
            output_tokens=500,
        )


def _happy_factory() -> ScriptedTransport:
    return ScriptedTransport([_SYLLABUS_OUT, _PLAN_OUT, _REFLECTION_OUT, _EXPLANATION_OUT])


def test_default_mode_is_offline_fixture(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main([])
    out = capsys.readouterr().out
    assert rc == 0
    assert "fixture mode (offline, no API calls)" in out
    assert out.count(" ok (") == 4


def test_live_without_key_refuses(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    rc = main(["--live"])
    captured = capsys.readouterr()
    assert rc == 1
    assert "ANTHROPIC_API_KEY" in captured.err


def test_live_happy_path_runs_all_four_nodes(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    rc = main(["--live"], transport_factory=_happy_factory)
    out = capsys.readouterr().out
    assert rc == 0
    assert out.count(" ok (") == 4
    assert "calls=4" in out
    assert "estimated_cost=$" in out
    assert "RAW_MARKER" not in out  # raw responses only behind --debug-raw


def test_call_cap_aborts_run(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Persistently invalid output burns the repair budget; the hard cap of
    5 API calls aborts the run before a sixth call is made."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    transport = ScriptedTransport([{"nope": True}] * 10)
    rc = main(["--live"], transport_factory=lambda: transport)
    out = capsys.readouterr().out
    assert rc == 1
    assert "ABORTED" in out
    assert "call cap" in out
    assert transport.calls == MAX_LIVE_CALLS  # the sixth call never happened


def test_cost_guard_aborts_before_first_call(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    transport = _happy_factory()
    rc = main(["--live", "--max-cost-usd", "0.000001"], transport_factory=lambda: transport)
    out = capsys.readouterr().out
    assert rc == 1
    assert "cost guard" in out
    assert transport.calls == 0  # aborted before any API call


def test_nonpositive_budget_rejected(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    rc = main(["--live", "--max-cost-usd", "0"], transport_factory=_happy_factory)
    captured = capsys.readouterr()
    assert rc == 1
    assert "must be positive" in captured.err


def test_debug_raw_prints_but_never_persists(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    calls_path = tmp_path / "calls.json"
    rc = main(
        ["--live", "--debug-raw", "--calls-out", str(calls_path)],
        transport_factory=_happy_factory,
    )
    out = capsys.readouterr().out
    assert rc == 0
    assert "RAW_MARKER" in out  # printed to stdout...
    written = calls_path.read_text(encoding="utf-8")
    assert "RAW_MARKER" not in written  # ...but never written to disk
    rows = json.loads(written)
    assert len(rows) == 4
    assert all(row["validation_outcome"] == "pass" for row in rows)
    assert all(row["prompt_hash"] for row in rows)


def test_calls_out_contains_no_prompt_content(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    calls_path = tmp_path / "calls.json"
    rc = main(["--live", "--calls-out", str(calls_path)], transport_factory=_happy_factory)
    capsys.readouterr()
    assert rc == 0
    written = calls_path.read_text(encoding="utf-8")
    # Sample-input content (calendar-ish constraints, goals) must not leak.
    assert "Backend SWE interview prep" not in written
    assert "deep_work_windows" not in written
    # Generated content must not leak either.
    assert "Review DP state definitions" not in written
