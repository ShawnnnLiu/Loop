"""Call-log readers over the production SQLite store (UX pass C3)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from agentic_calendar.common.sqlite import SqliteDatabase
from agentic_calendar.llm_nodes.call_log import (
    LlmCallLog,
    LlmNodeName,
    ValidationOutcome,
)
from agentic_calendar.llm_nodes.sqlite_call_log import SqliteLlmCallLogStore
from agentic_calendar.tools.llm_stats import main as stats_main
from agentic_calendar.tools.trace_llm_calls import main as trace_main


def _row(
    log_id: str,
    *,
    run_id: str = "run_1",
    attempt: int = 0,
    outcome: ValidationOutcome = ValidationOutcome.PASS,
    latency_ms: int = 1200,
    cache_hit: bool = False,
    created: datetime = datetime(2026, 7, 4, 9, 0, tzinfo=UTC),
) -> LlmCallLog:
    return LlmCallLog(
        llm_call_log_id=log_id,
        run_id=run_id,
        node=LlmNodeName.PLANNER,
        prompt_version="planner-v2-2026-06-23",
        model_name="claude-haiku-4-5",
        attempt=attempt,
        sdk_retry=0,
        input_tokens=1000,
        output_tokens=500,
        cost_estimate_usd=0.0035,
        latency_ms=latency_ms,
        validation_outcome=outcome,
        reason_code=None,
        cache_hit=cache_hit,
        truncated=False,
        refusal=False,
        prompt_hash="a" * 64,
        response_hash="b" * 64,
        created_at=created,
    )


def _seeded_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "app.db"
    store = SqliteLlmCallLogStore(SqliteDatabase(db_path))
    store.append(_row("c1", latency_ms=800, cache_hit=True))
    store.append(_row("c2", attempt=1, latency_ms=2400))
    store.append(
        _row(
            "c3",
            run_id="run_2",
            created=datetime(2026, 6, 1, 9, 0, tzinfo=UTC),
        )
    )
    return db_path


def test_trace_reads_the_sqlite_store_directly(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    db_path = _seeded_db(tmp_path)
    assert trace_main(["--db", str(db_path)]) == 0
    index = capsys.readouterr().out
    assert "run_1" in index and "run_2" in index

    assert trace_main(["--db", str(db_path), "--run-id", "run_1"]) == 0
    trace = capsys.readouterr().out
    assert "attempt=1" in trace
    assert "cache_hit" in trace


def test_stats_aggregates_and_date_filters(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    db_path = _seeded_db(tmp_path)
    assert stats_main(["--db", str(db_path)]) == 0
    out = capsys.readouterr().out
    assert "planner" in out
    assert "runs=2" in out  # run_1 + run_2

    # Date window excludes the June call.
    assert stats_main(["--db", str(db_path), "--since", "2026-07-01"]) == 0
    filtered = capsys.readouterr().out
    assert "runs=1" in filtered


def test_stats_and_trace_reject_a_missing_db(tmp_path: Path) -> None:
    missing = str(tmp_path / "nope.db")
    assert stats_main(["--db", missing]) == 1
    assert trace_main(["--db", missing]) == 1
