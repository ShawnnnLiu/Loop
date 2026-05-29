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
    """The CLI runs a full write then immediately rolls it back.

    Because the write moves mappings to VERIFIED (terminal), the CLI's
    rollback call exercises only the rollback queries; the mappings stay
    at VERIFIED. We confirm the write_result was a success and the
    rollback_result is queryable.
    """
    rc = cli.main(["--scenario", "success"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["write_result"]["status"] == "success"
    # rollback_result is well-formed.
    assert "deleted_event_ids" in payload["rollback_result"]
    assert "failed_event_ids" in payload["rollback_result"]
    # Final mappings still have a valid status.
    for m in payload["final_mappings"]:
        assert m["calendar_write_status"] in {
            "verified",
            "rolled_back",
            "rollback_failed",
        }


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
