"""Tests for the ``run_cycle`` operator CLI (Phase 9b).

Every ``main(argv)`` call here builds its own environment from the same
``--db`` path — exactly like separate operator invocations. The happy-path
test therefore *is* the restart-survival proof: state persisted by one
command must be sufficient for the next command in a fresh process-equivalent
environment. Fixture LLM mode keeps everything offline and deterministic.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from agentic_calendar.tools import run_cycle as cli
from agentic_calendar.tools.llm_smoke import sample_fixture_inputs

USER = "user_smoke"
"""The sample profile's user_id (``_SAMPLE_USER_PROFILE``)."""


def _write_onboard_file(tmp_path: Path) -> Path:
    """The onboarding bundle the CLI fixture mode expects (Backend SWE sample)."""
    profile = sample_fixture_inputs()[0].model_dump(mode="json")
    path = tmp_path / "onboard.json"
    path.write_text(json.dumps({"user_profile": profile, "timezone": "UTC"}))
    return path


def _run_json(
    capsys: pytest.CaptureFixture[str], argv: list[str]
) -> dict[str, Any]:
    """Invoke the CLI, require exit 0, and parse its single JSON document."""
    rc = cli.main(argv)
    captured = capsys.readouterr()
    assert rc == 0, f"expected exit 0 for {argv!r}; stderr: {captured.err!r}"
    payload = json.loads(captured.out)
    assert isinstance(payload, dict)
    return payload


def test_full_cycle_happy_path(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """onboard → propose → approve → write(dry) → write → ingest → status.

    Sequence matters: each command reconstructs its environment from the same
    SQLite path, so every step passing proves the previous step persisted all
    control-plane state the next one needs (typed states, never prose).
    """
    db = str(tmp_path / "cycle.db")
    onboard_file = _write_onboard_file(tmp_path)

    onboarded = _run_json(capsys, ["onboard", "--db", db, str(onboard_file)])
    assert onboarded["user_id"] == USER
    assert onboarded["created"] is True

    proposed = _run_json(
        capsys, ["propose", "--db", db, "--user", USER, "--llm", "fixture"]
    )
    assert proposed["state"] == "awaiting_user_approval"
    assert proposed["draft_payload_hash"].startswith("sha256:")

    approved = _run_json(capsys, ["approve", "--db", db, "--user", USER])
    assert approved["approval_event_id"] is not None

    dry = _run_json(capsys, ["write", "--db", db, "--user", USER, "--dry-run"])
    assert dry["dry_run"] is True
    assert dry["planned_event_count"] >= 1
    # A dry run is side-effect-free: the run stays approved, not written.
    assert dry["state"] == "calendar_write_approved"

    written = _run_json(capsys, ["write", "--db", db, "--user", USER])
    assert written["state"] == "active_plan"
    assert len(written["written_task_ids"]) >= 1
    statuses = written["mapping_status_by_task"]
    assert statuses, "a real write must record calendar event mappings"
    assert all(value == "verified" for value in statuses.values())

    telemetry = [
        {
            "telemetry_event_id": f"tel_{index:03d}",
            "task_id": task_id,
            "scheduled_duration_min": 60,
            "actual_duration_min": 80,
            "completed": True,
            "completion_timestamp": "2026-06-11T05:00:00+00:00",
            "user_reschedule_count": 0,
            "data_quality": "complete",
        }
        for index, task_id in enumerate(written["written_task_ids"], start=1)
    ]
    telemetry_file = tmp_path / "telemetry.json"
    telemetry_file.write_text(json.dumps(telemetry))
    ingested = _run_json(
        capsys, ["ingest", "--db", db, "--user", USER, str(telemetry_file)]
    )
    # Completing every task of the active plan ends the journey (axiom 02).
    assert ingested["state"] == "terminal_success"
    assert ingested["plan_completed"] is True

    status = _run_json(capsys, ["status", "--db", db, "--user", USER])
    assert status["onboarded"] is True
    assert status["active_plan_version"] is not None


def test_approve_before_any_propose_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """approve without a prior propose is an operator error, not a transition."""
    db = str(tmp_path / "cycle.db")
    rc = cli.main(["approve", "--db", db, "--user", USER])
    captured = capsys.readouterr()
    assert rc == 1
    assert "no run found" in captured.err


def test_propose_for_never_onboarded_user_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """propose requires an onboarding record; the error names the fix."""
    db = str(tmp_path / "cycle.db")
    rc = cli.main(["propose", "--db", db, "--user", "user_ghost"])
    captured = capsys.readouterr()
    assert rc == 1
    assert "onboard" in captured.err


def test_onboard_with_missing_file_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A missing payload file exits 1 with an error, never a traceback."""
    db = str(tmp_path / "cycle.db")
    rc = cli.main(["onboard", "--db", db, str(tmp_path / "does_not_exist.json")])
    captured = capsys.readouterr()
    assert rc == 1
    assert "error:" in captured.err


def test_status_on_onboarded_but_empty_db(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """status is read-only and works before any run exists: no state, onboarded."""
    db = str(tmp_path / "cycle.db")
    onboard_file = _write_onboard_file(tmp_path)
    _run_json(capsys, ["onboard", "--db", db, str(onboard_file)])

    status = _run_json(capsys, ["status", "--db", db, "--user", USER])
    assert status["onboarded"] is True
    assert status["state"] is None


def test_propose_live_without_api_key_fails_cleanly(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--llm live without ANTHROPIC_API_KEY exits 1 with a typed operator
    error naming the variable — never a raw SDK traceback (axiom 16: no raw
    exception crosses an operator surface)."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    db = str(tmp_path / "cycle.db")
    rc = cli.main(["propose", "--db", db, "--user", "user_ghost", "--llm", "live"])
    captured = capsys.readouterr()
    assert rc == 1
    assert "ANTHROPIC_API_KEY" in captured.err
