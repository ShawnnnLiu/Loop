"""Tests for the schema-export CLI."""

from __future__ import annotations

from pathlib import Path

import pytest

from agentic_calendar.tools.export_schemas import (
    CONTRACTS,
    build_schema,
    main,
    write_schemas,
)


def test_every_contract_registered() -> None:
    """The CONTRACTS dict must list every Pydantic contract the project ships.

    Phase 1 contracts: user/motivation profile, syllabus, task plan,
    validation result, scheduler output. Phase 2 contracts: draft schedule,
    approval event, calendar event mapping, plan diff. Phase 3 contracts:
    sponsor, sponsor report (+ input, approval), notification log. Phase 4
    contracts: telemetry, drift event, user duration multipliers. Phase 5
    contracts: source claim, strategy constraints, strategist input, company
    target, cache key, cache entry, milestone template. Phase 6 contracts:
    consent record, data access audit.
    """
    expected = {
        # Phase 1
        "user_profile",
        "motivation_profile",
        "syllabus_units",
        "task_plan",
        "validation_result",
        "scheduler_output",
        # Phase 2
        "draft_schedule",
        "approval_event",
        "calendar_event_mapping",
        "plan_diff",
        # Phase 3
        "sponsor",
        "sponsor_report",
        "sponsor_report_input",
        "sponsor_report_approval",
        "notification_log",
        # Phase 4
        "telemetry",
        "drift_event",
        "user_duration_multipliers",
        # Phase 5
        "source_claim",
        "strategy_constraints",
        "strategist_input",
        "company_target",
        "cache_key",
        "cache_entry",
        "milestone_template",
        # Phase 7
        "checkin_event",
        "accountability_contract",
        "accountability_state",
        "accountability_intervention",
        "nudge",
        "recommitment_request",
        "recommitment_event",
        # Phase 6
        "consent_record",
        "data_access_audit",
        "pooled_duration_model",
        "power_user_eligibility",
        "per_user_refinement",
        # Phase 8
        "llm_call_log",
        # Phase 9
        "threshold_change_log",
        # Loop: inbound calendar reconciliation
        "calendar_reconciliation",
        # Loop: completion / drop memory
        "task_disposition",
        # UX pass B5: durable reflections / explanations
        "prose_attachment",
        # Loop: grounding layer (corpus registry, G-A)
        "corpus_document",
        "corpus_snapshot",
    }
    assert set(CONTRACTS.keys()) == expected


@pytest.mark.parametrize("name", sorted(CONTRACTS.keys()))
def test_schemas_have_basic_shape(name: str) -> None:
    schema = build_schema(CONTRACTS[name])
    assert isinstance(schema, dict)
    assert "properties" in schema or "$ref" in schema or "$defs" in schema
    assert schema.get("type") == "object" or "$ref" in schema


def test_write_schemas_creates_files(tmp_path: Path) -> None:
    paths = write_schemas(tmp_path)
    assert len(paths) == len(CONTRACTS)
    for p in paths:
        assert p.exists()
        assert p.suffix == ".json"
        text = p.read_text(encoding="utf-8")
        assert text.endswith("\n")


def test_write_schemas_is_deterministic(tmp_path: Path) -> None:
    write_schemas(tmp_path)
    snapshot = {p.name: p.read_text(encoding="utf-8") for p in tmp_path.iterdir()}
    write_schemas(tmp_path)
    snapshot2 = {p.name: p.read_text(encoding="utf-8") for p in tmp_path.iterdir()}
    assert snapshot == snapshot2


def test_check_passes_after_write(tmp_path: Path) -> None:
    write_schemas(tmp_path)
    rc = main(["--out", str(tmp_path), "--check"])
    assert rc == 0


def test_check_detects_drift(tmp_path: Path) -> None:
    write_schemas(tmp_path)
    target = tmp_path / "task_plan.schema.json"
    target.write_text(target.read_text() + "// drift\n", encoding="utf-8")
    rc = main(["--out", str(tmp_path), "--check"])
    assert rc == 1


def test_check_fails_when_missing(tmp_path: Path) -> None:
    rc = main(["--out", str(tmp_path), "--check"])
    assert rc == 1
