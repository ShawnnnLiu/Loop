"""Tests for ``agentic_calendar.common.logging``."""

from __future__ import annotations

import logging

import pytest

from agentic_calendar.common.logging import correlated, get_logger, log_context


def test_get_logger_namespaces() -> None:
    log = get_logger("scheduler")
    assert log.name == "agentic_calendar.scheduler"


def test_get_logger_respects_already_namespaced_input() -> None:
    log = get_logger("agentic_calendar.scheduler.greedy")
    assert log.name == "agentic_calendar.scheduler.greedy"


def test_get_logger_rejects_empty() -> None:
    with pytest.raises(ValueError):
        get_logger("")


def test_correlated_attaches_ids_to_message(
    caplog: pytest.LogCaptureFixture,
) -> None:
    log = get_logger("scheduler.test")
    log.setLevel(logging.INFO)
    adapter = correlated(log, run_id="run_001", plan_version="plan_004")
    with caplog.at_level(logging.INFO, logger=log.name):
        adapter.info("scheduling started")
    assert any("run_id=run_001" in r.message for r in caplog.records)
    assert any("plan_version=plan_004" in r.message for r in caplog.records)


def test_correlated_drops_none_values() -> None:
    log = get_logger("validation.test")
    adapter = correlated(log, run_id="run_001", plan_version=None)
    msg, _kwargs = adapter.process("hello", {})
    assert "plan_version" not in msg  # None values omitted
    assert "run_id=run_001" in msg


def test_log_context_returns_correlated_adapter() -> None:
    log = get_logger("supervisor.test")
    with log_context(log, run_id="run_007", task_id="dp_002") as adapter:
        msg, _kwargs = adapter.process("routing", {})
    assert "run_id=run_007" in msg
    assert "task_id=dp_002" in msg
