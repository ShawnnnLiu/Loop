"""Tests for the server-rendered HTML pages (F0b).

Hosted mode end to end via ``TestClient``: the Google handshake is faked at the
``routes_auth`` seam and the write transport at the ``calendar_service`` seam,
so no network call happens. The CSRF token is read back out of the rendered
form and replayed, exercising the real session-bound CSRF check.
"""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

from agentic_calendar.app.web import calendar_service, routes_auth
from agentic_calendar.app.web.app import create_app
from agentic_calendar.app.web.config import WebAuthConfig
from agentic_calendar.common.secrets import TokenCipher
from agentic_calendar.tools.google_oauth_web import GoogleIdentity
from tests.app.test_cycle import _advance_past_draft, _canonical_profile, make_service
from tests.calendar_writer.test_google_adapter import FakeGoogleTransport

EMAIL = "tester@example.com"
SUB = "sub-pages"
TOKEN = {"token": "access", "refresh_token": "refresh"}
_CSRF_RE = re.compile(r'name="csrf_token" value="([^"]+)"')


def _config() -> WebAuthConfig:
    return WebAuthConfig(
        client_config={"web": {"client_id": "cid"}},
        redirect_uri="https://app.test/auth/callback",
        session_secret="unit-test-session-secret",
        audience="cid",
        tester_allowlist=frozenset({EMAIL}),
        https_only=False,
    )


def _client() -> TestClient:
    _service, env, _clock = make_service()
    return TestClient(
        create_app(env=env, auth_config=_config(), token_cipher=TokenCipher(TokenCipher.generate_key()))
    )


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


def _csrf(client: TestClient) -> str:
    match = _CSRF_RE.search(client.get("/home").text)
    assert match is not None
    return match.group(1)


def test_index_shows_login_when_unauthenticated() -> None:
    resp = _client().get("/")
    assert resp.status_code == 200
    assert "Connect Google Calendar" in resp.text


def test_index_redirects_home_when_authenticated(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client()
    _login(client, monkeypatch)
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/home"


def test_protected_page_redirects_when_unauthenticated() -> None:
    resp = _client().get("/home", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/"


def test_csrf_token_is_required(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client()
    _login(client, monkeypatch)
    _csrf(client)  # establish the session token
    resp = client.post("/ui/propose", data={"csrf_token": "forged"}, follow_redirects=False)
    assert resp.status_code == 403


def _onboard_form(token: str) -> dict[str, object]:
    return {
        "csrf_token": token,
        "goal": "Prepare for backend SWE interviews",
        "target_role": "Backend SWE",
        "target_companies": "Meta, Stripe",
        "target_level": "new_grad",
        "experience_level": "intermediate",
        "known_strengths": "arrays, hash maps",
        "known_weaknesses": "dynamic programming",
        "timeline_weeks": "10",
        "weekly_hours": "8",
        "preferred_session_length_min": "60",
        "max_session_length_min": "120",
        "dww_day": ["Mon", "Wed"],
        "dww_start": "18:00",
        "dww_end": "21:00",
        "no_events_before": "08:00",
        "no_events_after": "22:30",
        "max_daily_study_min": "180",
        "min_break_between_deep_blocks_min": "30",
        "allow_weekends": "on",
        "prefer_evening_sessions": "on",
        "timezone": "America/Los_Angeles",
    }


def test_onboard_page_renders_form(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client()
    _login(client, monkeypatch)
    resp = client.get("/onboard")
    assert resp.status_code == 200
    assert "Set up your profile" in resp.text
    assert 'name="goal"' in resp.text


def test_onboard_form_completes_onboarding(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client()
    _login(client, monkeypatch)
    assert "Set up your profile" in client.get("/home").text  # not onboarded yet

    resp = client.post(
        "/ui/onboard", data=_onboard_form(_csrf(client)), follow_redirects=False
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/home"
    assert "Propose a schedule" in client.get("/home").text


def test_onboard_form_prefills_saved_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client()
    _login(client, monkeypatch)
    client.post("/ui/onboard", data=_onboard_form(_csrf(client)), follow_redirects=False)

    # "Edit profile" must show what was saved, not the blank defaults.
    edit = client.get("/onboard").text
    assert 'value="Prepare for backend SWE interviews"' in edit
    assert 'value="Meta, Stripe"' in edit
    assert 'value="America/Los_Angeles"' in edit
    # The two selected deep-work weekdays come back checked.
    mon = re.search(r'name="dww_day" value="Mon"[^>]*>', edit)
    assert mon is not None and "checked" in mon.group(0)


def test_onboard_form_rejects_invalid_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client()
    _login(client, monkeypatch)
    bad = _onboard_form(_csrf(client))
    bad["no_events_before"] = "23:00"  # later than no_events_after -> contract rejects
    bad["no_events_after"] = "08:00"

    resp = client.post("/ui/onboard", data=bad, follow_redirects=False)
    assert resp.status_code == 400
    assert "must be earlier" in resp.text
    # The rejected submit did not onboard the user.
    assert "Set up your profile" in client.get("/home").text


def test_full_ui_journey(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client()
    _login(client, monkeypatch)
    client.post(
        "/api/onboard",
        json={"user_profile": _canonical_profile().model_dump(mode="json"), "timezone": "UTC"},
    )
    token = _csrf(client)

    proposed = client.post("/ui/propose", data={"csrf_token": token}, follow_redirects=False)
    assert proposed.status_code == 303
    assert proposed.headers["location"] == "/draft"

    draft = client.get("/draft")
    assert draft.status_code == 200
    assert "Canonical payload hash" in draft.text
    assert "Approve" in draft.text

    approved = client.post(
        "/ui/approve", data={"csrf_token": token, "action": "approve"}, follow_redirects=False
    )
    assert approved.status_code == 303
    assert "Write to my Google Calendar" in client.get("/draft").text

    transport = FakeGoogleTransport()
    monkeypatch.setattr(calendar_service, "build_service_from_token", lambda token_json: object())
    monkeypatch.setattr(calendar_service, "GoogleApiHttpTransport", lambda service: transport)

    written = client.post("/ui/write", data={"csrf_token": token}, follow_redirects=False)
    assert written.status_code == 303
    assert written.headers["location"] == "/home"
    assert "active_plan" in client.get("/home").text
    inserts = [cal for (method, cal) in transport.calls if method == "insert_event"]
    assert inserts and all(calendar_id == "cal_pages" for calendar_id in inserts)


def test_today_empty_without_active_plan(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client()
    _login(client, monkeypatch)
    client.post(
        "/api/onboard",
        json={"user_profile": _canonical_profile().model_dump(mode="json"), "timezone": "UTC"},
    )
    resp = client.get("/today")
    assert resp.status_code == 200
    assert "No active plan yet" in resp.text


def test_today_checkin_records_telemetry(monkeypatch: pytest.MonkeyPatch) -> None:
    _service, env, clock = make_service()
    client = TestClient(
        create_app(
            env=env, auth_config=_config(), token_cipher=TokenCipher(TokenCipher.generate_key())
        )
    )
    _login(client, monkeypatch)
    client.post(
        "/api/onboard",
        json={"user_profile": _canonical_profile().model_dump(mode="json"), "timezone": "UTC"},
    )
    token = _csrf(client)
    client.post("/ui/propose", data={"csrf_token": token})
    client.post("/ui/approve", data={"csrf_token": token, "action": "approve"})

    transport = FakeGoogleTransport()
    monkeypatch.setattr(calendar_service, "build_service_from_token", lambda token_json: object())
    monkeypatch.setattr(calendar_service, "GoogleApiHttpTransport", lambda service: transport)
    client.post("/ui/write", data={"csrf_token": token})

    # Before any task ends, the schedule is upcoming -> no check-in controls.
    assert "Mark complete" not in client.get("/today").text

    # Advance the frozen clock past every entry so each task becomes due.
    draft_id = client.get("/api/status").json()["draft_schedule_id"]
    _advance_past_draft(env, clock, draft_id)
    assert "Mark complete" in client.get("/today").text

    task_id = env.state.get_draft(draft_id).entries[0].task_id
    before = client.get("/api/status").json()["telemetry_event_count"]
    resp = client.post(
        "/ui/checkin",
        data={"csrf_token": token, "task_id": task_id, "outcome": "complete"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/today"
    assert client.get("/api/status").json()["telemetry_event_count"] == before + 1
    # The checked-off task now reads as reported instead of offering buttons.
    assert "reported" in client.get("/today").text


def test_checkin_ignores_task_not_in_plan(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client()
    _login(client, monkeypatch)
    client.post(
        "/api/onboard",
        json={"user_profile": _canonical_profile().model_dump(mode="json"), "timezone": "UTC"},
    )
    token = _csrf(client)
    # No active plan, so any task_id is a non-member: the POST is a no-op redirect.
    resp = client.post(
        "/ui/checkin",
        data={"csrf_token": token, "task_id": "not_a_task", "outcome": "complete"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert client.get("/api/status").json()["telemetry_event_count"] == 0
