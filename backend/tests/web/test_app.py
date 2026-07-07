"""HTTP-level tests for the Increment-1 FastAPI surface (F0a).

These prove the web layer faithfully wires to :class:`CycleService` and
preserves the deterministic contract: the same states, the same typed
``reason_code`` values, the same canonical payload hash the CLI emits — plus
the web-only concerns (status mapping, the user-id trust-boundary override).
The cycle *semantics* are tested exhaustively in ``tests/app/test_cycle.py``;
here we reuse its :func:`make_service` harness so the backing service is the
identical fixture-backed, claim-seeded, frozen-clock build.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from agentic_calendar.app.web.app import create_app
from agentic_calendar.calendar_writer.in_memory_adapter import (
    FailureModes,
    InMemoryCalendarAdapter,
)
from agentic_calendar.common.ids import DeterministicIdGenerator
from agentic_calendar.contracts.reason_codes import ReasonCode
from agentic_calendar.llm_nodes import LLMGenerationError
from tests.app.test_cycle import (
    PLAN_TASK_IDS,
    USER_ID,
    _advance_past_draft,
    _canonical_profile,
    _motivation_profile_payload,
    make_service,
)
from tests.app.test_extract_resume import FailingResumeIntake


def _client() -> tuple[TestClient, object]:
    _service, env, clock = make_service()
    app = create_app(env=env, default_user_id=USER_ID)
    return TestClient(app), clock


def test_healthz() -> None:
    client, _clock = _client()
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_status_reports_onboarded_user() -> None:
    client, _clock = _client()
    resp = client.get("/api/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["user_id"] == USER_ID
    assert body["onboarded"] is True
    assert body["timezone"] == "UTC"


def test_full_propose_approve_write_cycle() -> None:
    client, _clock = _client()

    proposed = client.post("/api/propose", json={})
    assert proposed.status_code == 200
    pbody = proposed.json()
    assert pbody["state"] == "awaiting_user_approval"
    assert pbody["scheduled_task_count"] == len(PLAN_TASK_IDS)
    # The draft-preview datum: a non-empty canonical payload hash the user
    # approves against (axiom 06).
    assert isinstance(pbody["draft_payload_hash"], str) and pbody["draft_payload_hash"]

    approved = client.post("/api/approve", json={})
    assert approved.status_code == 200
    abody = approved.json()
    assert abody["rejected"] is False
    assert abody["approval_event_id"]
    assert abody["approved_payload_hash"] == pbody["draft_payload_hash"]

    dry = client.post("/api/write", json={"dry_run": True})
    assert dry.status_code == 200
    dbody = dry.json()
    assert dbody["dry_run"] is True
    assert dbody["planned_event_count"] == len(PLAN_TASK_IDS)

    written = client.post("/api/write", json={})
    assert written.status_code == 200
    wbody = written.json()
    assert wbody["dry_run"] is False
    assert wbody["state"] == "active_plan"
    assert sorted(wbody["written_task_ids"]) == sorted(PLAN_TASK_IDS)
    assert sorted(wbody["verified_task_ids"]) == sorted(PLAN_TASK_IDS)


def test_command_precondition_failure_maps_to_409() -> None:
    client, _clock = _client()
    # approve before propose: a CycleError, not a workflow failure.
    resp = client.post("/api/approve", json={})
    assert resp.status_code == 409
    body = resp.json()
    assert body["type"] == "CycleError"
    assert "error" in body


def test_adjust_endpoint_applies_and_approve_locks_adjusted_hash() -> None:
    client, _clock = _client()
    proposed = client.post("/api/propose", json={}).json()

    resp = client.post(
        "/api/adjust",
        json={"adjustments": [{"task_id": "dp_001", "start": "2026-05-04T16:00:00+00:00"}]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["applied"] is True
    assert body["adjusted_task_ids"] == ["dp_001"]
    assert body["draft_payload_hash"] != proposed["draft_payload_hash"]

    # Approving after the adjust commits to the adjusted draft's hash.
    approved = client.post("/api/approve", json={}).json()
    assert approved["approved_payload_hash"] == body["draft_payload_hash"]


def test_adjust_endpoint_rejection_is_200_with_typed_reason() -> None:
    client, _clock = _client()
    client.post("/api/propose", json={})

    # 07:00 is before the profile's 08:00 bound — a workflow rejection (HTTP 200
    # with a typed reason_code), not a precondition error.
    resp = client.post(
        "/api/adjust",
        json={"adjustments": [{"task_id": "dp_001", "start": "2026-05-04T07:00:00+00:00"}]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["applied"] is False
    assert body["reason_code"] == "OUTSIDE_ALLOWED_HOURS"
    assert body["violations"]


def test_adjust_endpoint_advisory_move_applies_with_warnings() -> None:
    client, _clock = _client()
    client.post("/api/propose", json={})

    # Move dp_002 to Mon 16:30 — back-to-back BEFORE its prerequisite dp_001
    # (Mon 18:00). In allowed hours, no overlap, Mon load 60+90=150<180: the only
    # fault is ordering, which is advisory (ADR-0008), not a refusal.
    resp = client.post(
        "/api/adjust",
        json={"adjustments": [{"task_id": "dp_002", "start": "2026-05-04T16:30:00+00:00"}]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["applied"] is True
    assert body["reason_code"] is None
    assert [w["reason_code"] for w in body["warnings"]] == ["DEPENDENCY_ADVISORY"]


def test_drop_endpoint_produces_draft_then_approve_write() -> None:
    client, _clock = _client()
    client.post("/api/propose", json={})
    client.post("/api/approve", json={})
    client.post("/api/write", json={})

    resp = client.post("/api/drop", json={"task_ids": ["dp_001"]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["state"] == "awaiting_user_approval"
    assert body["dropped_task_ids"] == ["dp_001"]
    assert body["survivor_task_count"] == 1

    client.post("/api/approve", json={})
    written = client.post("/api/write", json={})
    assert written.status_code == 200
    assert written.json()["state"] == "active_plan"


def test_adjust_before_propose_maps_to_409() -> None:
    client, _clock = _client()
    resp = client.post(
        "/api/adjust",
        json={"adjustments": [{"task_id": "dp_001", "start": "2026-05-04T16:00:00+00:00"}]},
    )
    assert resp.status_code == 409
    assert resp.json()["type"] == "CycleError"


def test_onboard_overrides_client_supplied_user_id() -> None:
    client, _clock = _client()
    payload = _canonical_profile().model_dump(mode="json")
    payload["user_id"] = "intruder_999"  # must be ignored in favor of the acting user
    resp = client.post(
        "/api/onboard",
        json={"user_profile": payload, "timezone": "UTC"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["user_id"] == USER_ID
    # user_123 was already onboarded by make_service, so this is an update.
    assert body["created"] is False


def test_invalid_onboard_payload_maps_to_422() -> None:
    client, _clock = _client()
    resp = client.post("/api/onboard", json={"user_profile": {"user_id": "x"}})
    assert resp.status_code == 422
    body = resp.json()
    assert body["type"] == "ValidationError"


# --------------------------------------------------------------------------- #
# Read projections + guarded check-in (F-A): the JSON the SPA renders from.
# --------------------------------------------------------------------------- #


def test_read_endpoints_expose_projections() -> None:
    client, _clock = _client()

    me = client.get("/api/me")
    assert me.status_code == 200
    mbody = me.json()
    assert mbody["onboarded"] is True
    assert mbody["timezone"] == "UTC"
    assert mbody["profile"]["target_role"] == "Backend SWE"

    today = client.get("/api/today")
    assert today.status_code == 200
    assert today.json()["tasks"] == []  # no active plan yet

    draft = client.get("/api/draft")
    assert draft.status_code == 200
    dbody = draft.json()
    assert dbody["draft"] is None
    assert dbody["hash_canonicalization_version"]
    # Dev mode has no per-user calendar credential → server-side free/busy empty.
    assert dbody["free_busy"] == []

    thresholds = client.get("/api/thresholds")
    assert thresholds.status_code == 200
    assert thresholds.json()["sections"]

    acct = client.get("/api/accountability")
    assert acct.status_code == 200
    assert acct.json()["has_motivation_profile"] is False  # empty-state (axiom 21)


def test_draft_endpoint_exposes_pending_draft_with_approval_hash() -> None:
    client, _clock = _client()
    proposed = client.post("/api/propose", json={})
    assert proposed.status_code == 200

    draft = client.get("/api/draft")
    assert draft.status_code == 200
    dbody = draft.json()
    assert dbody["draft"] is not None
    # The grid renders against the same canonical hash the user approves (axiom 06).
    assert dbody["payload_hash"] == proposed.json()["draft_payload_hash"]
    assert {entry["task_id"] for entry in dbody["draft"]["entries"]} == set(PLAN_TASK_IDS)


def test_checkin_records_completion_once_block_is_due() -> None:
    client, clock = _client()
    client.post("/api/propose", json={})
    client.post("/api/approve", json={})
    assert client.post("/api/write", json={}).status_code == 200
    # Advance past every scheduled block so the tasks are "due".
    clock.advance(seconds=8 * 86400)

    resp = client.post("/api/checkin", json={"task_id": "dp_001", "outcome": "complete"})
    assert resp.status_code == 200
    assert resp.json()["ingested_count"] == 1

    today = client.get("/api/today").json()
    row = next(r for r in today["tasks"] if r["task_id"] == "dp_001")
    assert row["reported"] is True


def test_checkin_before_block_due_maps_to_409() -> None:
    client, _clock = _client()
    client.post("/api/propose", json={})
    client.post("/api/approve", json={})
    client.post("/api/write", json={})
    # No clock advance: the block is still in the future, so it is not yet due.
    resp = client.post("/api/checkin", json={"task_id": "dp_001", "outcome": "complete"})
    assert resp.status_code == 409


def test_checkin_invalid_outcome_maps_to_422() -> None:
    client, _clock = _client()
    resp = client.post("/api/checkin", json={"task_id": "dp_001", "outcome": "kinda"})
    assert resp.status_code == 422


def test_propose_honors_body_free_busy_in_dev() -> None:
    """Dev mode trusts the body's free_busy (the operator/test surface keeps
    control). An all-horizon busy block leaves no room, so scheduling fails with
    a typed reason_code — proving the supplied list flows through the route.
    (Hosted mode instead fetches free/busy server-side; see routes_cycle.)"""
    client, clock = _client()
    now = clock.now()
    busy = [{"start": now.isoformat(), "end": (now + timedelta(days=14)).isoformat()}]
    resp = client.post("/api/propose", json={"free_busy": busy, "horizon_days": 14})
    assert resp.status_code == 200
    assert resp.json()["reason_code"]


def _activate(client: TestClient) -> None:
    assert client.post("/api/propose", json={}).status_code == 200
    assert client.post("/api/approve", json={}).status_code == 200
    assert client.post("/api/write", json={}).json()["state"] == "active_plan"


def test_calendar_sync_toggle_round_trips_through_me() -> None:
    client, _clock = _client()
    assert client.get("/api/me").json()["inbound_calendar_sync_enabled"] is False

    resp = client.post("/api/calendar-sync", json={"enabled": True})
    assert resp.status_code == 200
    assert resp.json()["inbound_calendar_sync_enabled"] is True
    assert client.get("/api/me").json()["inbound_calendar_sync_enabled"] is True

    off = client.post("/api/calendar-sync", json={"enabled": False})
    assert off.json()["inbound_calendar_sync_enabled"] is False


def test_reconcile_is_sync_disabled_until_opted_in() -> None:
    client, _clock = _client()
    _activate(client)
    body = client.post("/api/reconcile").json()
    assert body["outcome"] == "sync_disabled"
    assert body["deltas"] == []


def test_reconcile_opted_in_with_no_edits_is_no_change() -> None:
    client, _clock = _client()
    _activate(client)
    client.post("/api/calendar-sync", json={"enabled": True})
    body = client.post("/api/reconcile").json()
    assert body["outcome"] == "no_change"


# Write-failure recovery routes (UX pass B1): the SPA's rollback / retry
# affordances over a run parked in calendar_write_failed.


def _failed_write_client() -> tuple[TestClient, InMemoryCalendarAdapter]:
    adapter = InMemoryCalendarAdapter(
        id_generator=DeterministicIdGenerator(),
        failure_modes=FailureModes(corrupt_metadata_for_task_ids=frozenset({"dp_001"})),
    )
    _service, env, _clock = make_service(calendar_adapter=adapter)
    app = create_app(env=env, default_user_id=USER_ID)
    client = TestClient(app)
    client.post("/api/propose", json={})
    client.post("/api/approve", json={})
    failed = client.post("/api/write", json={}).json()
    assert failed["state"] == "calendar_write_failed"
    adapter.set_failure_modes(FailureModes())
    return client, adapter


def test_rollback_route_dry_run_counts_then_full_rollback_exits() -> None:
    client, _adapter = _failed_write_client()

    dry = client.post("/api/rollback", json={"dry_run": True})
    assert dry.status_code == 200
    dbody = dry.json()
    assert dbody["dry_run"] is True
    assert dbody["rollbackable_event_count"] == len(PLAN_TASK_IDS)
    assert dbody["state"] == "calendar_write_failed"

    done = client.post("/api/rollback", json={})
    assert done.status_code == 200
    body = done.json()
    assert body["fully_rolled_back"] is True
    assert body["state"] == "error_requires_user"
    assert len(body["deleted_event_ids"]) == len(PLAN_TASK_IDS)


def test_retry_write_route_recovers_to_active_plan() -> None:
    client, _adapter = _failed_write_client()

    resp = client.post("/api/retry-write", json={})
    assert resp.status_code == 200
    body = resp.json()
    assert body["state"] == "active_plan"
    assert sorted(body["verified_task_ids"]) == sorted(PLAN_TASK_IDS)


def test_recovery_routes_outside_failure_state_map_to_409() -> None:
    client, _clock = _client()
    client.post("/api/propose", json={})
    assert client.post("/api/rollback", json={}).status_code == 409
    assert client.post("/api/retry-write", json={}).status_code == 409


# Accountability loop routes (UX pass B3): weekly check-in + recommitment.


def test_weekly_checkin_route_round_trips_through_accountability_view() -> None:
    _service, env, clock = make_service(motivation_profile=_motivation_profile_payload())
    client = TestClient(create_app(env=env, default_user_id=USER_ID))
    proposed = client.post("/api/propose", json={}).json()
    client.post("/api/approve", json={})
    client.post("/api/write", json={})
    _advance_past_draft(env, clock, proposed["draft_schedule_id"])

    assert client.get("/api/accountability").json()["checkin_due"] is True

    resp = client.post("/api/weekly-checkin", json={"blockers": "travel"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["checkin_status"] == "completed"

    view = client.get("/api/accountability").json()
    assert view["checkin_due"] is False
    assert view["checkin_status"] == "completed"


def test_recommit_route_without_open_ask_maps_to_409() -> None:
    _service, env, _clock = make_service(motivation_profile=_motivation_profile_payload())
    client = TestClient(create_app(env=env, default_user_id=USER_ID))
    client.post("/api/propose", json={})
    resp = client.post("/api/recommit", json={"choice": "keep_plan"})
    assert resp.status_code == 409


# Résumé extraction (RI-C): the persistence-free onboarding extract endpoint.


_EXTRACT_BODY = {
    "resume_text": (
        "Senior Backend Engineer at Acme Corp (2019-2024)\n"
        "Led the billing platform team; Python and Go services on Kubernetes."
    ),
    "draft_context": {"target_role": "Backend SWE"},
}


def test_extract_route_returns_proposal_with_normalized_skills() -> None:
    client, _clock = _client()
    resp = client.post("/api/onboard/extract", json=_EXTRACT_BODY)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["run_id"].startswith("intake-")
    assert body["taxonomy_version"] == "skill-taxonomy-v1"
    assert body["proposal"]["skills"]
    assert {s["skill_id"] for s in body["skills_canonical"]} >= {
        "skill.python",
        "skill.go",
        "skill.kubernetes",
    }


def test_extract_route_rejects_short_resume_with_422() -> None:
    client, _clock = _client()
    resp = client.post("/api/onboard/extract", json={"resume_text": "too short"})
    assert resp.status_code == 422
    assert resp.json()["type"] == "ValidationError"


def test_extract_route_ignores_body_user_id() -> None:
    client, _clock = _client()
    resp = client.post(
        "/api/onboard/extract", json={**_EXTRACT_BODY, "user_id": "intruder_999"}
    )
    assert resp.status_code == 200
    assert resp.json()["user_id"] == USER_ID


def test_extract_route_surfaces_llm_failure_as_200_with_reason_code() -> None:
    failing = FailingResumeIntake(
        LLMGenerationError("refused", reason_code=ReasonCode.LLM_REFUSAL)
    )
    _service, env, _clock = make_service(resume_intake=failing)
    client = TestClient(create_app(env=env, default_user_id=USER_ID))
    resp = client.post("/api/onboard/extract", json=_EXTRACT_BODY)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "failed"
    assert body["reason_code"] == "LLM_REFUSAL"
    assert body["proposal"] is None


def test_extract_route_persists_nothing(tmp_path: Path) -> None:
    """The persistence-free contract at the HTTP level: no ``app_documents``
    row appears after an extract (the only write path stays /api/onboard)."""
    _service, env, _clock = make_service(db_path=tmp_path / "app.db")
    client = TestClient(create_app(env=env, default_user_id=USER_ID))
    assert env.db is not None

    def row_count() -> int:
        with env.db.read() as cursor:
            cursor.execute("SELECT COUNT(*) FROM app_documents")
            return int(cursor.fetchone()[0])

    before = row_count()
    assert client.post("/api/onboard/extract", json=_EXTRACT_BODY).status_code == 200
    assert row_count() == before
