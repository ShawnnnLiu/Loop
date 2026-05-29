"""Tests for the ``rollback_calendar`` operator CLI (Phase 2)."""

from __future__ import annotations

import json

import pytest

from agentic_calendar.tools import rollback_calendar as cli


def test_list_returns_zero(capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli.main(["--list"])
    assert rc == 0
    assert "success" in capsys.readouterr().out


def test_rollback_success_path_marks_everything_rolled_back(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The CLI runs a full write then rolls it back; every mapping must
    end ROLLED_BACK and every external event must be deleted."""
    rc = cli.main(["--scenario", "success"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["write_result"]["status"] == "success"
    assert payload["rollback_result"]["fully_rolled_back"] is True
    assert payload["rollback_result"]["failed_event_ids"] == []
    # Every mapping is actually rolled back (axiom 06 lines 132-137).
    assert payload["final_mappings"], "expected non-empty final_mappings"
    for m in payload["final_mappings"]:
        assert m["calendar_write_status"] == "rolled_back"
    # Adapter delete actually fired for every event written.
    assert len(payload["rollback_result"]["deleted_event_ids"]) == len(
        payload["final_mappings"]
    )


def test_rollback_byte_stable(capsys: pytest.CaptureFixture[str]) -> None:
    cli.main(["--scenario", "success"])
    first = capsys.readouterr().out
    cli.main(["--scenario", "success"])
    second = capsys.readouterr().out
    assert first == second


def test_rollback_unknown_scenario_returns_nonzero(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc = cli.main(["--scenario", "does_not_exist"])
    assert rc == 1
    assert "unknown scenario" in capsys.readouterr().err


def test_rollback_no_scenario_errors() -> None:
    with pytest.raises(SystemExit):
        cli.main([])
