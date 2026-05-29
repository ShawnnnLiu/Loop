"""Tests for the ``verify_calendar`` operator CLI (Phase 2)."""

from __future__ import annotations

import json

import pytest

from agentic_calendar.tools import verify_calendar as cli


def test_list_returns_zero(capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli.main(["--list"])
    assert rc == 0
    assert "success" in capsys.readouterr().out


def test_verify_success_path(capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli.main(["--scenario", "success"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["verification"]["all_verified"] is True
    assert len(payload["verification"]["failed_task_ids"]) == 0


def test_verify_with_dropped_task_fails(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc = cli.main(["--scenario", "success", "--drop-task-id", "dp_001"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["verification"]["all_verified"] is False
    assert "dp_001" in payload["verification"]["failed_task_ids"]


def test_verify_with_corrupted_metadata_fails(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc = cli.main(["--scenario", "success", "--corrupt-task-id", "dp_001"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["verification"]["all_verified"] is False


def test_verify_byte_stable(capsys: pytest.CaptureFixture[str]) -> None:
    cli.main(["--scenario", "success"])
    first = capsys.readouterr().out
    cli.main(["--scenario", "success"])
    second = capsys.readouterr().out
    assert first == second


def test_verify_unknown_scenario_returns_nonzero(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc = cli.main(["--scenario", "does_not_exist"])
    assert rc == 1
    assert "unknown scenario" in capsys.readouterr().err


def test_verify_no_scenario_errors() -> None:
    with pytest.raises(SystemExit):
        cli.main([])
