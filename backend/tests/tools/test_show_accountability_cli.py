"""Tests for the completion-dashboard CLI (``show_accountability``)."""

from __future__ import annotations

import json
from pathlib import Path

from agentic_calendar.tools.show_accountability import main


def _payload() -> dict:
    profile = {
        "motivation_profile_id": "mot_1",
        "user_id": "user_123",
        "profile_version": "v1",
        "self_motivation_level": "medium",
        "procrastination_risk": "high",
        "pressure_tolerance": "medium",
        "weekly_checkin_enabled": False,
        "created_at": "2026-04-28T12:00:00-07:00",
        "updated_at": "2026-04-28T12:00:00-07:00",
    }
    events = [
        {
            "telemetry_event_id": f"tel_{i}",
            "task_id": f"t{i}",
            "scheduled_duration_min": 60,
            "actual_duration_min": 60,
            "completed": True,
            "completion_timestamp": "2026-05-10T18:00:00-07:00",
            "user_reschedule_count": 0,
            "data_quality": "complete",
        }
        for i in range(4)
    ] + [
        {
            "telemetry_event_id": "tel_miss_0",
            "task_id": "t_miss_0",
            "scheduled_duration_min": 60,
            "completed": False,
            "user_reschedule_count": 1,
            "data_quality": "complete",
        },
        {
            "telemetry_event_id": "tel_miss_1",
            "task_id": "t_miss_1",
            "scheduled_duration_min": 60,
            "completed": False,
            "user_reschedule_count": 0,
            "data_quality": "complete",
        },
    ]
    return {
        "profile": profile,
        "plan_id": "plan_004",
        "timezone": "America/Los_Angeles",
        "events_7d": events,
        "events_14d": events,
        "checkin_events": [],
        "scheduled_minutes_due": 360,
        "completed_minutes_due": 295,
    }


def _write(tmp_path: Path, payload: dict) -> Path:
    path = tmp_path / "state.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_human_readable_dashboard(tmp_path: Path, capsys) -> None:
    path = _write(tmp_path, _payload())
    code = main([str(path), "--at", "2026-05-11T12:00:00-07:00"])
    out = capsys.readouterr().out
    assert code == 0
    assert "missed_tasks_7d:         2" in out
    assert "behind_schedule_percent: 18" in out
    assert "intervention:            send_user_nudge (MISSED_TASK_THRESHOLD_REACHED)" in out
    assert "policy_audit:" in out
    assert "[MATCH] missed_task_warning" in out


def test_json_mode_round_trips(tmp_path: Path, capsys) -> None:
    path = _write(tmp_path, _payload())
    code = main([str(path), "--at", "2026-05-11T12:00:00-07:00", "--json"])
    assert code == 0
    data = json.loads(capsys.readouterr().out)
    assert data["state"]["missed_tasks_7d"] == 2
    assert data["decision"]["reason_code"] == "MISSED_TASK_THRESHOLD_REACHED"
    assert len(data["decision"]["evaluations"]) == 5


def test_inactive_flag_short_circuits(tmp_path: Path, capsys) -> None:
    path = _write(tmp_path, _payload())
    code = main([str(path), "--at", "2026-05-11T12:00:00-07:00", "--inactive", "--json"])
    assert code == 0
    data = json.loads(capsys.readouterr().out)
    assert data["decision"]["reason_code"] == "ACCOUNTABILITY_CONTRACT_INACTIVE"
    assert data["decision"]["evaluations"] == []


def test_invalid_timezone_fails_cleanly(tmp_path: Path, capsys) -> None:
    payload = _payload()
    payload["timezone"] = "Mars/Olympus_Mons"
    path = _write(tmp_path, payload)
    code = main([str(path)])
    assert code == 1
    assert "timezone" in capsys.readouterr().err


def test_naive_at_timestamp_rejected(tmp_path: Path, capsys) -> None:
    path = _write(tmp_path, _payload())
    code = main([str(path), "--at", "2026-05-11T12:00:00"])
    assert code == 1
    assert "timezone-aware" in capsys.readouterr().err


def test_invalid_profile_rejected(tmp_path: Path, capsys) -> None:
    payload = _payload()
    payload["profile"]["sponsor_enabled"] = True  # no sponsor_id → invalid
    path = _write(tmp_path, payload)
    code = main([str(path)])
    assert code == 1
    assert "sponsor" in capsys.readouterr().err
