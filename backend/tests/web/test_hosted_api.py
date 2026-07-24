"""Hosted-mode ``/api`` tests — the surface the React SPA drives (F-H cutover).

These replace the retired Jinja page/``/ui`` tests with their ``/api``
equivalents, exercised end to end through ``TestClient`` against a real session.
The Google handshake is faked at the ``routes_auth`` seam and the write
transport at the ``calendar_service`` seam, so no network call happens. Every
mutation is a normal ``/api`` call subject to the same server checks the SPA
faces — there is no privileged path, so an axiom-06 invariant cannot be bypassed
from the client.

The cycle *semantics* are tested exhaustively in ``tests/app/test_cycle.py`` and
the dev-mode ``/api`` wiring in ``test_app.py``; here the focus is the hosted
journey (session-derived user, per-user calendar) plus the read projections.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

from agentic_calendar.app.tuning import TUNABLE_SECTIONS, scalar_fields
from agentic_calendar.app.web import calendar_service, routes_auth
from agentic_calendar.app.web.app import create_app
from agentic_calendar.app.web.config import WebAuthConfig
from agentic_calendar.app.web.routes_auth import _user_id_for_sub
from agentic_calendar.calendar_writer.google_adapter import GoogleCalendarApiError
from agentic_calendar.common.secrets import TokenCipher
from agentic_calendar.contracts.threshold_change_log import ThresholdChange
from agentic_calendar.tools.google_oauth_web import GoogleIdentity
from tests.app.test_cycle import (
    PLAN_TASK_IDS,
    _advance_past_draft,
    _canonical_profile,
    _motivation_profile_payload,
    make_service,
)
from tests.calendar_writer.test_google_adapter import FakeGoogleTransport

EMAIL = "tester@example.com"
SUB = "sub-pages"
TOKEN = {"token": "access", "refresh_token": "refresh"}


def _config() -> WebAuthConfig:
    return WebAuthConfig(
        client_config={"web": {"client_id": "cid"}},
        redirect_uri="https://app.test/auth/callback",
        session_secret="unit-test-session-secret",
        audience="cid",
        tester_allowlist=frozenset({EMAIL}),
        https_only=False,
    )


def _client() -> tuple[TestClient, Any, Any]:
    _service, env, clock = make_service()
    client = TestClient(
        create_app(env=env, auth_config=_config(), token_cipher=TokenCipher(TokenCipher.generate_key()))
    )
    return client, env, clock


def _login(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        routes_auth,
        "build_authorization_url",
        lambda *, client_config, redirect_uri, state: (
            f"https://g.test/auth?state={state}",
            "test-verifier",
        ),
    )
    monkeypatch.setattr(routes_auth, "exchange_code", lambda **kwargs: dict(TOKEN))
    monkeypatch.setattr(
        routes_auth,
        "identity_from_token",
        lambda token_json, *, audience: GoogleIdentity(sub=SUB, email=EMAIL),
    )
    monkeypatch.setattr(routes_auth, "build_service_from_token", lambda token_json: object())
    monkeypatch.setattr(
        routes_auth,
        "create_dedicated_calendar",
        lambda service, *, summary, time_zone="UTC": "cal_pages",
    )
    state = parse_qs(
        urlparse(client.get("/auth/login", follow_redirects=False).headers["location"]).query
    )["state"][0]
    client.get(f"/auth/callback?code=c&state={state}", follow_redirects=False)


def _onboard(client: TestClient, **extra: Any) -> None:
    client.post(
        "/api/onboard",
        json={
            "user_profile": _canonical_profile().model_dump(mode="json"),
            "timezone": "UTC",
            **extra,
        },
    )


def _install_write_transport(monkeypatch: pytest.MonkeyPatch) -> FakeGoogleTransport:
    transport = FakeGoogleTransport()
    monkeypatch.setattr(calendar_service, "build_service_from_token", lambda token_json: object())
    monkeypatch.setattr(calendar_service, "GoogleApiHttpTransport", lambda service: transport)
    return transport


# --------------------------------------------------------------------------- #
# Auth boundary
# --------------------------------------------------------------------------- #


def test_api_is_session_gated_when_unauthenticated() -> None:
    client, _env, _clock = _client()
    # No session: the trust boundary refuses the read (the SPA turns this into a
    # redirect to /auth/login).
    assert client.get("/api/me", follow_redirects=False).status_code == 401


# --------------------------------------------------------------------------- #
# E2E smoke: the full SPA loop through /api (onboard → propose → adjust →
# approve → write), proving the approved-hash recheck holds at write time.
# --------------------------------------------------------------------------- #


def test_e2e_onboard_propose_adjust_approve_write(monkeypatch: pytest.MonkeyPatch) -> None:
    client, _env, _clock = _client()
    _login(client, monkeypatch)
    _onboard(client)

    proposed = client.post("/api/propose", json={}).json()
    assert proposed["state"] == "awaiting_user_approval"
    assert proposed["scheduled_task_count"] == len(PLAN_TASK_IDS)

    # Drag one block to a new, valid time. The server re-validates and persists a
    # new draft with a fresh canonical hash (the client never decides validity).
    adjusted = client.post(
        "/api/adjust",
        json={"adjustments": [{"task_id": "dp_001", "start": "2026-05-04T16:00:00+00:00"}]},
    ).json()
    assert adjusted["applied"] is True
    assert adjusted["draft_payload_hash"] != proposed["draft_payload_hash"]

    # Approve commits to the ADJUSTED draft's hash — that is the hash the write
    # rechecks against the live draft (axiom 06).
    approved = client.post("/api/approve", json={}).json()
    assert approved["approval_event_id"]
    assert approved["approved_payload_hash"] == adjusted["draft_payload_hash"]

    transport = _install_write_transport(monkeypatch)
    written = client.post("/api/write", json={}).json()
    assert written["state"] == "active_plan"
    assert written["reason_code"] is None
    # Every planned event was written AND verified after the fact.
    assert sorted(written["written_task_ids"]) == sorted(PLAN_TASK_IDS)
    assert sorted(written["verified_task_ids"]) == sorted(PLAN_TASK_IDS)
    # Each insert landed on THIS user's dedicated calendar, never another.
    inserts = [cal for (method, cal) in transport.calls if method == "insert_event"]
    assert inserts and all(calendar_id == "cal_pages" for calendar_id in inserts)


def test_write_failure_returns_typed_reason_through_api(monkeypatch: pytest.MonkeyPatch) -> None:
    """A failed calendar write is a 200 with a typed reason_code at the HTTP
    boundary (not an exception), the plan is NOT activated, and nothing verifies
    — the SPA renders this as a failure, never a (non-existent) auto-rollback."""
    client, _env, _clock = _client()
    _login(client, monkeypatch)
    _onboard(client)
    client.post("/api/propose", json={})
    client.post("/api/approve", json={})

    transport = _install_write_transport(monkeypatch)
    # Make the very first calendar insert fail at the adapter seam.
    transport.fail_insert = GoogleCalendarApiError("events.insert failed: backend error", status=500)

    written = client.post("/api/write", json={})
    assert written.status_code == 200
    body = written.json()
    assert body["reason_code"] is not None
    assert body["state"] != "active_plan"  # the plan was not activated
    assert body["verified_task_ids"] == []
    assert body["write_status"] != "success"


def test_propose_feeds_server_side_free_busy(monkeypatch: pytest.MonkeyPatch) -> None:
    client, _env, _clock = _client()
    _login(client, monkeypatch)
    profile = _canonical_profile()
    _onboard(client)

    captured: dict[str, Any] = {}

    def _fake_fetch(
        env_: Any, *, user_id: str, token_cipher: Any, time_min: Any, time_max: Any, **_: Any
    ) -> list[dict[str, str]]:
        captured["window"] = (time_min, time_max)
        # A real (non-empty) busy list, dated before the horizon so it can't
        # affect placement — we only assert it flows through without breaking.
        return [{"start": "2020-01-01T01:00:00+00:00", "end": "2020-01-01T03:00:00+00:00"}]

    monkeypatch.setattr(calendar_service, "fetch_user_free_busy", _fake_fetch)

    proposed = client.post("/api/propose", json={})
    assert proposed.status_code == 200
    assert proposed.json()["state"] == "awaiting_user_approval"
    # Propose asked for busy ranges spanning the whole plan horizon (server-side;
    # the SPA never supplies free/busy).
    time_min, time_max = captured["window"]
    assert time_max - time_min == timedelta(days=profile.timeline_weeks * 7)


def test_free_busy_is_served_in_the_users_wall_clock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Google freebusy returns UTC instants, but the SPA grid draws the
    wall-clock digits embedded in the ISO string — served as UTC, a 2-3PM PDT
    personal event painted at 9-10PM. The server must restamp intervals in the
    user's timezone before they cross the API."""
    client, _env, _clock = _client()
    _login(client, monkeypatch)
    _onboard(client, timezone="America/Los_Angeles")

    captured: dict[str, Any] = {}

    class _FreeBusyTransport:
        def query_free_busy(
            self, *, calendar_ids: Any, time_min: datetime, time_max: datetime
        ) -> list[tuple[datetime, datetime]]:
            captured["calendar_ids"] = list(calendar_ids)
            # 2026-07-03 2-3PM PDT, exactly as Google reports it: in UTC.
            return [
                (
                    datetime(2026, 7, 3, 21, 0, tzinfo=UTC),
                    datetime(2026, 7, 3, 22, 0, tzinfo=UTC),
                )
            ]

    monkeypatch.setattr(calendar_service, "build_service_from_token", lambda token_json: object())
    monkeypatch.setattr(
        calendar_service, "GoogleApiHttpTransport", lambda service: _FreeBusyTransport()
    )

    view = client.get("/api/draft").json()
    # Same instants, the user's wall clock — and non-empty, so a failure inside
    # the best-effort wrapper can't silently pass as [].
    assert view["free_busy"] == [
        {"start": "2026-07-03T14:00:00-07:00", "end": "2026-07-03T15:00:00-07:00"}
    ]
    # Availability spans the user's own commitments (primary) *and* the tasks we
    # previously placed (their dedicated calendar), so re-plans don't double-book.
    assert captured["calendar_ids"] == ["primary", "cal_pages"]


# --------------------------------------------------------------------------- #
# Onboarding projection (résumé round-trip via /api/me)
# --------------------------------------------------------------------------- #


def test_onboard_resume_text_round_trips_through_api(monkeypatch: pytest.MonkeyPatch) -> None:
    client, _env, _clock = _client()
    _login(client, monkeypatch)
    profile = _canonical_profile().model_dump(mode="json")
    profile["resume_text"] = "RESUME_MARKER 4 yrs Python and Go"
    client.post("/api/onboard", json={"user_profile": profile, "timezone": "UTC"})

    me = client.get("/api/me").json()
    assert me["onboarded"] is True
    assert me["email"] == EMAIL
    assert me["profile"]["resume_text"] == "RESUME_MARKER 4 yrs Python and Go"


def test_onboard_omitted_resume_is_null(monkeypatch: pytest.MonkeyPatch) -> None:
    client, _env, _clock = _client()
    _login(client, monkeypatch)
    _onboard(client)  # the canonical profile leaves resume_text unset
    assert client.get("/api/me").json()["profile"]["resume_text"] is None


# --------------------------------------------------------------------------- #
# Today / check-in projection
# --------------------------------------------------------------------------- #


def test_today_empty_without_active_plan(monkeypatch: pytest.MonkeyPatch) -> None:
    client, _env, _clock = _client()
    _login(client, monkeypatch)
    _onboard(client)
    today = client.get("/api/today")
    assert today.status_code == 200
    assert today.json()["tasks"] == []


def test_today_checkin_records_telemetry_once_due(monkeypatch: pytest.MonkeyPatch) -> None:
    client, env, clock = _client()
    _login(client, monkeypatch)
    _onboard(client)
    client.post("/api/propose", json={})
    client.post("/api/approve", json={})
    _install_write_transport(monkeypatch)
    client.post("/api/write", json={})

    draft_id = client.get("/api/status").json()["draft_schedule_id"]
    # Before any block ends, every task is upcoming (not yet due) and not reported.
    upcoming = client.get("/api/today").json()["tasks"]
    assert upcoming and all(not row["due"] and not row["reported"] for row in upcoming)

    _advance_past_draft(env, clock, draft_id)
    task_id = env.state.get_draft(draft_id).entries[0].task_id
    before = client.get("/api/status").json()["telemetry_event_count"]

    resp = client.post("/api/checkin", json={"task_id": task_id, "outcome": "complete"})
    assert resp.status_code == 200
    assert client.get("/api/status").json()["telemetry_event_count"] == before + 1
    # The checked-off task now reads as reported.
    row = next(r for r in client.get("/api/today").json()["tasks"] if r["task_id"] == task_id)
    assert row["reported"] is True


def test_checkin_foreign_task_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    client, _env, _clock = _client()
    _login(client, monkeypatch)
    _onboard(client)
    # No active plan, so any task_id is a non-member: the guard refuses it (409),
    # so the SPA cannot report a foreign or non-due task.
    resp = client.post("/api/checkin", json={"task_id": "not_a_task", "outcome": "complete"})
    assert resp.status_code == 409
    assert client.get("/api/status").json()["telemetry_event_count"] == 0


# --------------------------------------------------------------------------- #
# Accountability projection (empty-state first; full snapshot when set up)
# --------------------------------------------------------------------------- #


def test_accountability_empty_without_motivation_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    client, _env, _clock = _client()
    _login(client, monkeypatch)
    _onboard(client)  # no motivation profile (the opt-in gate)
    acct = client.get("/api/accountability").json()
    assert acct["has_motivation_profile"] is False
    assert acct["state"] is None
    assert acct["decision"] is None


def test_accountability_snapshot_renders_with_motivation_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, env, clock = _client()
    _login(client, monkeypatch)
    # The onboard route rebinds user_profile.user_id to the session user but not
    # the motivation profile, whose user_id the contract requires to match.
    acting_user = _user_id_for_sub(SUB)
    motivation = {**_motivation_profile_payload(), "user_id": acting_user}
    _onboard(client, motivation_profile=motivation)
    client.post("/api/propose", json={})
    client.post("/api/approve", json={})
    _install_write_transport(monkeypatch)
    client.post("/api/write", json={})

    # Advance past every entry and check one task off, so real completion
    # telemetry flows into the deterministic projection the dashboard renders.
    draft_id = client.get("/api/status").json()["draft_schedule_id"]
    _advance_past_draft(env, clock, draft_id)
    task_id = env.state.get_draft(draft_id).entries[0].task_id
    client.post("/api/checkin", json={"task_id": task_id, "outcome": "complete"})

    acct = client.get("/api/accountability").json()
    assert acct["has_motivation_profile"] is True
    # The deterministic snapshot is present with its computed fields.
    assert acct["state"] is not None
    assert acct["state"]["current_status"]
    assert "completion_rate_7d" in acct["state"]
    assert acct["decision"] is not None


# --------------------------------------------------------------------------- #
# Thresholds projection (read-only; defaults + journaled change)
# --------------------------------------------------------------------------- #


def test_thresholds_expose_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    client, _env, _clock = _client()
    _login(client, monkeypatch)
    body = client.get("/api/thresholds").json()
    served_sections = {section["name"] for section in body["sections"]}
    assert served_sections == set(TUNABLE_SECTIONS)
    # With no tuning file applied, every value serves the code default.
    assert all(
        field["status"] == "default"
        for section in body["sections"]
        for field in section["fields"]
    )
    assert body["history"] == []


def test_thresholds_expose_journaled_change(monkeypatch: pytest.MonkeyPatch) -> None:
    client, env, clock = _client()
    _login(client, monkeypatch)
    # Seed one journaled change directly into the append-only log (the only
    # writer in production is apply_tuning; the projection only reads).
    section = "drift_thresholds"
    config_type, default = TUNABLE_SECTIONS[section]
    field = next(iter(scalar_fields(config_type)))
    prior = getattr(default, field)
    env.threshold_log_store.append(
        ThresholdChange(
            change_id="thrchg_test",
            config_section=section,
            threshold_field=field,
            prior_value=prior,
            new_value=prior + 1,
            effective_at=clock.now(),
            justification="dogfood calibration round 1",
            dataset_reference="tuning.toml",
        )
    )
    body = client.get("/api/thresholds").json()
    assert len(body["history"]) == 1
    change = body["history"][0]
    assert change["config_section"] == section
    assert change["threshold_field"] == field
    assert change["justification"] == "dogfood calibration round 1"
