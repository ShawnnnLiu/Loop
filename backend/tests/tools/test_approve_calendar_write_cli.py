"""Tests for the ``approve_calendar_write`` operator CLI (Phase 2)."""

from __future__ import annotations

import json

import pytest

from agentic_calendar.tools import approve_calendar_write as cli


def test_list_returns_zero(capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli.main(["--list"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "success" in out


def test_approve_emits_well_formed_approval_event(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc = cli.main(["--scenario", "success"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["approval_event_id"].startswith("approval_")
    assert payload["user_id"] == "user_demo"
    assert payload["plan_id"] == "plan_success"
    assert payload["action_type"] == "add_to_calendar"
    assert payload["approved_payload_hash"].startswith("sha256:")
    assert payload["hash_algorithm"] == "sha256"
    assert payload["hash_canonicalization_version"] == "v1"
    assert payload["created_at"] == "2026-05-04T17:55:00Z"
    assert payload["expires_at"] == "2026-05-05T17:55:00Z"


def test_approve_is_deterministic(capsys: pytest.CaptureFixture[str]) -> None:
    cli.main(["--scenario", "success"])
    first = capsys.readouterr().out
    cli.main(["--scenario", "success"])
    second = capsys.readouterr().out
    assert first == second


def test_approve_unknown_scenario_returns_nonzero(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc = cli.main(["--scenario", "does_not_exist"])
    assert rc == 1
    assert "unknown scenario" in capsys.readouterr().err


def test_approve_no_scenario_errors() -> None:
    with pytest.raises(SystemExit):
        cli.main([])
