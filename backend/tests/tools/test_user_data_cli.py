"""Tests for the data-control CLI (``user_data``)."""

from __future__ import annotations

import json
from pathlib import Path

from agentic_calendar.tools.user_data import main


def _payload() -> dict:
    return {
        "consent_records": [
            {
                "consent_record_id": "consent_001",
                "user_id": "user_123",
                "scope": "pooled_training",
                "status": "granted",
                "consent_version": "2026-06",
                "granted_at": "2026-06-01T09:00:00-07:00",
                "revoked_at": None,
                "created_at": "2026-06-01T09:00:00-07:00",
                "updated_at": "2026-06-01T09:00:00-07:00",
            },
            {
                "consent_record_id": "consent_002",
                "user_id": "user_456",
                "scope": "cohort_retrieval",
                "status": "revoked",
                "consent_version": "2026-06",
                "granted_at": "2026-06-01T09:00:00-07:00",
                "revoked_at": "2026-06-05T09:00:00-07:00",
                "created_at": "2026-06-01T09:00:00-07:00",
                "updated_at": "2026-06-05T09:00:00-07:00",
            },
        ],
        "data_access_audit": [
            {
                "audit_entry_id": "audit_prior_001",
                "user_id": "user_123",
                "purpose": "pooled_training",
                "accessor": "training_pipeline",
                "outcome": "allowed",
                "reason_code": None,
                "created_at": "2026-06-08T09:00:00-07:00",
            }
        ],
        "stores": {
            "telemetry": {
                "user_123": [
                    {
                        "telemetry_event_id": "tel_001",
                        "task_id": "task_a1",
                        "scheduled_duration_min": 60,
                        "completed": False,
                        "user_reschedule_count": 0,
                        "data_quality": "complete",
                    },
                    {
                        "telemetry_event_id": "tel_002",
                        "task_id": "task_a2",
                        "scheduled_duration_min": 90,
                        "completed": False,
                        "user_reschedule_count": 1,
                        "data_quality": "complete",
                    },
                ],
                "user_456": [
                    {
                        "telemetry_event_id": "tel_003",
                        "task_id": "task_b1",
                        "scheduled_duration_min": 45,
                        "completed": False,
                        "user_reschedule_count": 0,
                        "data_quality": "complete",
                    }
                ],
            }
        },
    }


def _write(tmp_path: Path, payload: dict) -> Path:
    path = tmp_path / "user_data.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


AT = "2026-06-10T09:00:00-07:00"


def test_view_summarizes_consent_and_counts(tmp_path: Path, capsys) -> None:
    path = _write(tmp_path, _payload())
    code = main([str(path), "view", "--user", "user_123", "--at", AT])
    out = capsys.readouterr().out
    assert code == 0
    assert "consent pooled_training: granted (version 2026-06)" in out
    assert "telemetry: 2 row(s)" in out
    assert "data_access_audit: 1 entr(ies)" in out


def test_export_emits_all_and_only_the_users_data(tmp_path: Path, capsys) -> None:
    path = _write(tmp_path, _payload())
    code = main([str(path), "export", "--user", "user_123", "--at", AT])
    assert code == 0
    bundle = json.loads(capsys.readouterr().out)
    assert bundle["user_id"] == "user_123"
    assert {r["telemetry_event_id"] for r in bundle["stores"]["telemetry"]} == {
        "tel_001",
        "tel_002",
    }
    assert {r["consent_record_id"] for r in bundle["consent_records"]} == {"consent_001"}
    assert [e["audit_entry_id"] for e in bundle["data_access_audit"]] == ["audit_prior_001"]


def test_delete_reports_counts_and_audit(tmp_path: Path, capsys) -> None:
    path = _write(tmp_path, _payload())
    code = main([str(path), "delete", "--user", "user_123", "--at", AT])
    out = capsys.readouterr().out
    assert code == 0
    assert "telemetry: 2 row(s) removed" in out
    assert "consent_records: 1 row(s) removed" in out
    assert "(DATA_DELETED)" in out


def test_invalid_consent_record_fails_cleanly(tmp_path: Path, capsys) -> None:
    payload = _payload()
    payload["consent_records"][0]["status"] = "revoked"  # revoked w/o revoked_at
    path = _write(tmp_path, payload)
    code = main([str(path), "view", "--user", "user_123", "--at", AT])
    assert code == 1
    assert "revoked status requires revoked_at" in capsys.readouterr().err


def test_naive_at_timestamp_rejected(tmp_path: Path, capsys) -> None:
    path = _write(tmp_path, _payload())
    code = main([str(path), "view", "--user", "user_123", "--at", "2026-06-10T09:00:00"])
    assert code == 1
    assert "timezone-aware" in capsys.readouterr().err


def test_malformed_stores_shape_rejected(tmp_path: Path, capsys) -> None:
    payload = _payload()
    payload["stores"]["telemetry"] = ["not", "a", "mapping"]
    path = _write(tmp_path, payload)
    code = main([str(path), "view", "--user", "user_123", "--at", AT])
    assert code == 1
    assert "must map user ids" in capsys.readouterr().err
