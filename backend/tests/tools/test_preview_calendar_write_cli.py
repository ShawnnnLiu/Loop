"""Tests for the ``preview_calendar_write`` operator CLI (Phase 2)."""

from __future__ import annotations

import json

import pytest

from agentic_calendar.tools import preview_calendar_write as cli


@pytest.fixture
def captured(capsys: pytest.CaptureFixture[str]) -> pytest.CaptureFixture[str]:
    return capsys


def test_list_scenarios_returns_zero(captured: pytest.CaptureFixture[str]) -> None:
    rc = cli.main(["--list"])
    assert rc == 0
    out = captured.readouterr().out
    assert "success" in out
    assert "fragmented" in out


def test_preview_success_emits_hash_and_events(
    captured: pytest.CaptureFixture[str],
) -> None:
    rc = cli.main(["--scenario", "success"])
    assert rc == 0
    payload = json.loads(captured.readouterr().out)
    assert payload["draft_payload_hash"].startswith("sha256:")
    assert len(payload["draft_payload_hash"]) == len("sha256:") + 64
    assert len(payload["planned_events"]) >= 1
    for pe in payload["planned_events"]:
        md = pe["metadata"]
        assert md["app"] == "career_scheduler"
        assert md["plan_version"] == "plan_success"


def test_preview_byte_stable_across_runs(
    captured: pytest.CaptureFixture[str],
) -> None:
    """Same scenario + frozen clock = byte-identical stdout."""
    cli.main(["--scenario", "success"])
    first = captured.readouterr().out
    cli.main(["--scenario", "success"])
    second = captured.readouterr().out
    assert first == second


def test_preview_unknown_scenario_returns_nonzero(
    captured: pytest.CaptureFixture[str],
) -> None:
    rc = cli.main(["--scenario", "does_not_exist"])
    assert rc == 1
    err = captured.readouterr().err
    assert "unknown scenario" in err


def test_preview_no_scenario_errors(
    captured: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit):
        cli.main([])


def test_preview_does_not_call_adapter() -> None:
    """Smoke-level: preview is pure; verify by running the success scenario
    and confirming that calling preview multiple times yields the same hash."""
    # First call.
    from agentic_calendar.tools._calendar_cli_common import (
        build_draft_for_scenario,
        make_environment,
    )

    env = make_environment()
    draft = build_draft_for_scenario("success", env)
    result1 = env.manager.preview(draft=draft, target_calendar_id="primary")
    result2 = env.manager.preview(draft=draft, target_calendar_id="primary")
    assert result1.draft_payload_hash == result2.draft_payload_hash
    # Adapter still has no events.
    assert env.adapter.all_events() == []
