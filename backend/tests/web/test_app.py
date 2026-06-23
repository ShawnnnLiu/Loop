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

from fastapi.testclient import TestClient

from agentic_calendar.app.web.app import create_app
from tests.app.test_cycle import (
    PLAN_TASK_IDS,
    USER_ID,
    _canonical_profile,
    make_service,
)


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
