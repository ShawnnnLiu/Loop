"""Tests for the ``LlmCallLogStore`` implementations.

The behavioral suite is parametrized over the in-memory and SQLite
implementations (Phase 9a): both must satisfy the protocol identically.
The restart-survival test at the bottom is SQLite-only by nature.

Contract-level fixture coverage lives in ``test_call_log.py``; this module
covers only store behavior.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from agentic_calendar.common.sqlite import SqliteDatabase
from agentic_calendar.llm_nodes.call_log import (
    InMemoryLlmCallLogStore,
    LlmCallLog,
    LlmCallLogAlreadyExistsError,
    LlmCallLogStore,
)
from agentic_calendar.llm_nodes.sqlite_call_log import SqliteLlmCallLogStore


@pytest.fixture(params=["in_memory", "sqlite"])
def store(request: pytest.FixtureRequest, tmp_path: Path) -> LlmCallLogStore:
    if request.param == "sqlite":
        return SqliteLlmCallLogStore(SqliteDatabase(tmp_path / "store.db"))
    return InMemoryLlmCallLogStore()


def _make_log(log_id: str, run_id: str = "run_t") -> LlmCallLog:
    # Same minimal valid payload shape as ``test_call_log.py``.
    return LlmCallLog.model_validate(
        {
            "llm_call_log_id": log_id,
            "run_id": run_id,
            "node": "planner",
            "prompt_version": "planner-2026-06-01",
            "model_name": "claude-haiku-4-5-20251001",
            "attempt": 0,
            "input_tokens": 6000,
            "output_tokens": 7000,
            # Non-zero cache tiers so every round-trip test below proves the
            # counts survive persistence, not just default back to 0.
            "cache_creation_tokens": 512,
            "cache_read_tokens": 2048,
            "cost_estimate_usd": 0.005,
            "latency_ms": 9000,
            "validation_outcome": "pass",
            "created_at": "2026-06-10T14:05:00-07:00",
        }
    )


def test_satisfies_protocol(store: LlmCallLogStore) -> None:
    assert isinstance(store, LlmCallLogStore)


def test_append_and_list_round_trip(store: LlmCallLogStore) -> None:
    log = _make_log("llmcall_001")
    store.append(log)
    assert store.list_all() == [log]
    assert store.list_for_run("run_t") == [log]
    # Cache-tier counts round-trip explicitly (not just via model equality).
    reread = store.list_all()[0]
    assert (reread.cache_creation_tokens, reread.cache_read_tokens) == (512, 2048)


def test_append_rejects_duplicate_id(store: LlmCallLogStore) -> None:
    log = _make_log("llmcall_dup")
    store.append(log)
    with pytest.raises(LlmCallLogAlreadyExistsError):
        store.append(log)
    assert len(store.list_all()) == 1


def test_list_for_run_filters_and_preserves_insertion_order(
    store: LlmCallLogStore,
) -> None:
    a = _make_log("llmcall_a", run_id="run_1")
    b = _make_log("llmcall_b", run_id="run_2")
    c = _make_log("llmcall_c", run_id="run_1")
    store.append(a)
    store.append(b)
    store.append(c)
    assert store.list_for_run("run_1") == [a, c]
    assert store.list_for_run("run_2") == [b]
    assert store.list_for_run("run_missing") == []


def test_list_all_preserves_insertion_order(store: LlmCallLogStore) -> None:
    logs = [_make_log(f"llmcall_{i:03d}", run_id=f"run_{i % 2}") for i in range(5)]
    for log in logs:
        store.append(log)
    assert store.list_all() == logs


# --------------------------------------------------------------------------- #
# Restart survival (SQLite-only by nature): state written before a process
# exit must be fully recovered by a fresh store instance on the same file.
# --------------------------------------------------------------------------- #


def test_sqlite_state_survives_restart(tmp_path: Path) -> None:
    db_path = tmp_path / "store.db"
    db = SqliteDatabase(db_path)
    first = SqliteLlmCallLogStore(db)
    a = _make_log("llmcall_a", run_id="run_1")
    b = _make_log("llmcall_b", run_id="run_2")
    first.append(a)
    first.append(b)
    db.close()

    reopened = SqliteLlmCallLogStore(SqliteDatabase(db_path))
    assert reopened.list_all() == [a, b]
    assert reopened.list_for_run("run_1") == [a]
