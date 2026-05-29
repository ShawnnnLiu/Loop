"""Tests for the ``write_calendar`` operator CLI (Phase 2)."""

from __future__ import annotations

import json

import pytest

from agentic_calendar.tools import write_calendar as cli


def test_list_returns_zero(capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli.main(["--list"])
    assert rc == 0
    assert "success" in capsys.readouterr().out


def test_write_success_path(capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli.main(["--scenario", "success"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["mode"] == "write"
    assert payload["result"]["status"] == "success"
    assert payload["result"]["reason_code"] is None
    assert payload["result"]["run_id"].startswith("run_")
    # All mappings end VERIFIED.
    for m in payload["final_mappings"]:
        assert m["calendar_write_status"] == "verified"


def test_write_dry_run_emits_preview(capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli.main(["--scenario", "success", "--dry-run"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["mode"] == "dry_run"
    assert "preview" in payload
    assert payload["preview"]["draft_payload_hash"].startswith("sha256:")


def test_write_with_dropped_task_yields_partial_failure(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc = cli.main(["--scenario", "success", "--drop-task-id", "dp_001"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["result"]["status"] == "partial_failure"
    assert payload["result"]["reason_code"] == "EXTERNAL_SYNC_FAILED"
    statuses = {m["task_id"]: m["calendar_write_status"] for m in payload["final_mappings"]}
    assert statuses["dp_001"] == "verification_failed"


def test_write_with_failed_create_yields_calendar_write_failed(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc = cli.main(["--scenario", "success", "--fail-task-id", "dp_001"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["result"]["status"] == "partial_failure"
    assert payload["result"]["reason_code"] == "CALENDAR_WRITE_FAILED"


def test_write_byte_stable(capsys: pytest.CaptureFixture[str]) -> None:
    cli.main(["--scenario", "success"])
    first = capsys.readouterr().out
    cli.main(["--scenario", "success"])
    second = capsys.readouterr().out
    assert first == second


def test_write_unknown_scenario_returns_nonzero(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc = cli.main(["--scenario", "does_not_exist"])
    assert rc == 1
    assert "unknown scenario" in capsys.readouterr().err


def test_write_no_scenario_errors() -> None:
    with pytest.raises(SystemExit):
        cli.main([])
