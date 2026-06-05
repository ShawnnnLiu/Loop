"""Smoke tests for the Phase 4 operator CLIs.

Each CLI is invoked via its ``main(argv)`` entry point with a tmp_path fixture
file, matching the test style of the Phase 2/3 CLI tests.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agentic_calendar.tools import classify_drift as drift_cli
from agentic_calendar.tools import ingest_telemetry as ingest_cli
from agentic_calendar.tools import propose_replan as replan_cli
from agentic_calendar.tools import show_metrics as metrics_cli

# ---------------------------------------------------------------------------
# Shared fixture payloads
# ---------------------------------------------------------------------------

_TELEMETRY_COMPLETE = {
    "telemetry_event_id": "tel_smoke_001",
    "task_id": "dp_002",
    "scheduled_duration_min": 90,
    "actual_duration_min": 135,
    "completed": True,
    "completion_timestamp": "2026-05-06T20:42:00-07:00",
    "user_reschedule_count": 2,
    "subjective_difficulty": 4,
    "data_quality": "complete",
    "duration_estimated": False,
    "captured_offline": False,
    "synced_at": "2026-05-06T20:43:00-07:00",
}

_TELEMETRY_INCOMPLETE = {
    "telemetry_event_id": "tel_smoke_002",
    "task_id": "dp_001",
    "scheduled_duration_min": 60,
    "actual_duration_min": None,
    "completed": False,
    "completion_timestamp": None,
    "user_reschedule_count": 0,
    "data_quality": "complete",
    "duration_estimated": False,
    "captured_offline": False,
}

# Minimal TaskPlan for drift / replan tests.
_TASK_PLAN = {
    "plan_version": "plan_smoke_v1",
    "tasks": [
        {
            "task_id": "dp_001",
            "module_id": "dp",
            "title": "Review DP",
            "estimated_duration_min": 60,
            "cognitive_load": 3,
            "category": "concept_review",
            "required_focus_level": "medium",
        },
        {
            "task_id": "dp_002",
            "module_id": "dp",
            "title": "Practice DP",
            "estimated_duration_min": 90,
            "cognitive_load": 4,
            "category": "practice",
            "required_focus_level": "deep",
        },
    ],
}

# PlanVersion wrapping the above TaskPlan.
_PLAN_VERSION = {
    "plan_version": "plan_smoke_v1",
    "user_id": "user_smoke",
    "state": "active",
    "plan": _TASK_PLAN,
    "created_at": "2026-05-01T00:00:00+00:00",
    "updated_at": "2026-05-01T00:00:00+00:00",
}

_MULTIPLIERS = {
    "user_id": "user_smoke",
    "computed_at": "2026-05-10T08:00:00+00:00",
    "multipliers": [
        {
            "category": "practice",
            "multiplier": 1.50,
            "sample_size": 6,
            "observed_ratio": 1.50,
        }
    ],
}


# ---------------------------------------------------------------------------
# A. ingest_telemetry
# ---------------------------------------------------------------------------


def test_ingest_single_payload_returns_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    f = tmp_path / "payload.json"
    f.write_text(json.dumps(_TELEMETRY_COMPLETE), encoding="utf-8")
    rc = ingest_cli.main([str(f)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "ingested" in out


def test_ingest_list_of_payloads_returns_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    payloads = [
        {**_TELEMETRY_COMPLETE, "telemetry_event_id": "tel_list_001"},
        {**_TELEMETRY_INCOMPLETE, "telemetry_event_id": "tel_list_002"},
    ]
    f = tmp_path / "payloads.json"
    f.write_text(json.dumps(payloads), encoding="utf-8")
    rc = ingest_cli.main([str(f)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "ingested" in out


def test_ingest_duplicate_shows_duplicate(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    payloads = [_TELEMETRY_COMPLETE, _TELEMETRY_COMPLETE]
    f = tmp_path / "dupes.json"
    f.write_text(json.dumps(payloads), encoding="utf-8")
    rc = ingest_cli.main([str(f)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "duplicate" in out


def test_ingest_privacy_violation_returns_nonzero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A payload with calendar_event_title must be rejected (privacy rule)."""
    bad = {
        **_TELEMETRY_COMPLETE,
        "telemetry_event_id": "tel_bad_001",
        "calendar_event_title": "My study session",
    }
    f = tmp_path / "bad.json"
    f.write_text(json.dumps(bad), encoding="utf-8")
    rc = ingest_cli.main([str(f)])
    assert rc != 0
    out = capsys.readouterr().out
    assert "rejected" in out


def test_ingest_invalid_json_returns_nonzero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    f = tmp_path / "broken.json"
    f.write_text("{not valid json", encoding="utf-8")
    rc = ingest_cli.main([str(f)])
    assert rc != 0


def test_ingest_missing_file_returns_nonzero(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc = ingest_cli.main(["/nonexistent/path/payload.json"])
    assert rc != 0


# ---------------------------------------------------------------------------
# B. show_metrics
# ---------------------------------------------------------------------------


def test_show_metrics_returns_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    f = tmp_path / "events.json"
    f.write_text(
        json.dumps({"events": [_TELEMETRY_COMPLETE]}), encoding="utf-8"
    )
    rc = metrics_cli.main([str(f)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "completion_rate" in out


def test_show_metrics_json_flag(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    f = tmp_path / "events.json"
    f.write_text(
        json.dumps({"events": [_TELEMETRY_COMPLETE]}), encoding="utf-8"
    )
    rc = metrics_cli.main([str(f), "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert "sample_size" in payload
    assert "completion_rate" in payload
    assert payload["sample_size"] == 1
    assert payload["completed_count"] == 1


def test_show_metrics_empty_events(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    f = tmp_path / "empty.json"
    f.write_text(json.dumps({"events": []}), encoding="utf-8")
    rc = metrics_cli.main([str(f)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "sample_size" in out


def test_show_metrics_missing_events_key_returns_nonzero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    f = tmp_path / "nokey.json"
    f.write_text(json.dumps({"other": []}), encoding="utf-8")
    rc = metrics_cli.main([str(f)])
    assert rc != 0


# ---------------------------------------------------------------------------
# C. classify_drift
# ---------------------------------------------------------------------------

def _drift_input_no_drift() -> dict:
    """Input that produces no drift: one completed task, no threshold crossed."""
    return {
        "plan": _TASK_PLAN,
        "events": [_TELEMETRY_COMPLETE],
    }


def _drift_input_capacity_mismatch() -> dict:
    """Supply 3 weekly cycles all well below completion floor to trigger CAPACITY_MISMATCH."""
    return {
        "plan": _TASK_PLAN,
        "events": [_TELEMETRY_COMPLETE],
        "weekly_cycles": [
            {"scheduled_min": 300, "completed_min": 60},
            {"scheduled_min": 300, "completed_min": 60},
            {"scheduled_min": 300, "completed_min": 60},
        ],
    }


def test_classify_drift_no_drift(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    f = tmp_path / "input.json"
    f.write_text(json.dumps(_drift_input_no_drift()), encoding="utf-8")
    rc = drift_cli.main([str(f)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "no drift detected" in out


def test_classify_drift_capacity_mismatch(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    f = tmp_path / "cap.json"
    f.write_text(json.dumps(_drift_input_capacity_mismatch()), encoding="utf-8")
    rc = drift_cli.main([str(f)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "capacity_mismatch" in out


def test_classify_drift_json_flag(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    f = tmp_path / "cap.json"
    f.write_text(json.dumps(_drift_input_capacity_mismatch()), encoding="utf-8")
    rc = drift_cli.main([str(f), "--json"])
    assert rc == 0
    events = json.loads(capsys.readouterr().out)
    assert isinstance(events, list)
    assert len(events) >= 1
    assert events[0]["drift_type"] == "capacity_mismatch"


def test_classify_drift_invalid_plan_returns_nonzero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bad = {"plan": {"plan_version": ""}, "events": []}
    f = tmp_path / "bad.json"
    f.write_text(json.dumps(bad), encoding="utf-8")
    rc = drift_cli.main([str(f)])
    assert rc != 0


def test_classify_drift_missing_plan_key_returns_nonzero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    f = tmp_path / "noplan.json"
    f.write_text(json.dumps({"events": []}), encoding="utf-8")
    rc = drift_cli.main([str(f)])
    assert rc != 0


# ---------------------------------------------------------------------------
# D. propose_replan
# ---------------------------------------------------------------------------


def test_propose_replan_with_change(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    payload = {"active_plan": _PLAN_VERSION, "multipliers": _MULTIPLIERS}
    f = tmp_path / "replan.json"
    f.write_text(json.dumps(payload), encoding="utf-8")
    rc = replan_cli.main([str(f)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "draft plan_version" in out
    assert "tasks_with_duration_changes" in out


def test_propose_replan_json_flag(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    payload = {"active_plan": _PLAN_VERSION, "multipliers": _MULTIPLIERS}
    f = tmp_path / "replan.json"
    f.write_text(json.dumps(payload), encoding="utf-8")
    rc = replan_cli.main([str(f), "--json"])
    assert rc == 0
    diff = json.loads(capsys.readouterr().out)
    assert "summary" in diff
    assert diff["summary"]["tasks_with_duration_changes"] >= 1


def test_propose_replan_no_change(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A 1.0 multiplier (no change) prints the 'nothing to recalibrate' message."""
    mult_no_change = {
        "user_id": "user_smoke",
        "computed_at": "2026-05-10T08:00:00+00:00",
        "multipliers": [
            {
                "category": "practice",
                "multiplier": 1.0,
                "sample_size": 6,
                "observed_ratio": 1.0,
            }
        ],
    }
    payload = {"active_plan": _PLAN_VERSION, "multipliers": mult_no_change}
    f = tmp_path / "noop.json"
    f.write_text(json.dumps(payload), encoding="utf-8")
    rc = replan_cli.main([str(f)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "nothing to recalibrate" in out


def test_propose_replan_missing_multipliers_key_returns_nonzero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    payload = {"active_plan": _PLAN_VERSION}
    f = tmp_path / "nomult.json"
    f.write_text(json.dumps(payload), encoding="utf-8")
    rc = replan_cli.main([str(f)])
    assert rc != 0


def test_propose_replan_invalid_plan_version_returns_nonzero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bad_plan = {**_PLAN_VERSION, "plan_version": ""}
    payload = {"active_plan": bad_plan, "multipliers": _MULTIPLIERS}
    f = tmp_path / "badplan.json"
    f.write_text(json.dumps(payload), encoding="utf-8")
    rc = replan_cli.main([str(f)])
    assert rc != 0
