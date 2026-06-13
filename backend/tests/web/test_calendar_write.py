"""Tests for the hosted per-user calendar write path (Increment 4).

The Google handshake (connect) and the write-path transport are both faked at
their seams, so no network call happens. The write goes through the *real*
``GoogleCalendarAdapter`` over the existing ``FakeGoogleTransport``, proving
the per-user adapter is wired in and that every event lands on the signed-in
user's own dedicated calendar — never another's.
"""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

from agentic_calendar.app.cycle import CycleError
from agentic_calendar.app.web import calendar_service, routes_auth
from agentic_calendar.app.web.app import create_app
from agentic_calendar.app.web.calendar_service import build_user_calendar_service
from agentic_calendar.app.web.config import WebAuthConfig
from agentic_calendar.common.secrets import TokenCipher
from agentic_calendar.tools.google_oauth_web import GoogleIdentity
from tests.app.test_cycle import PLAN_TASK_IDS, _canonical_profile, make_service
from tests.calendar_writer.test_google_adapter import FakeGoogleTransport

SUB = "sub-user-a"
EMAIL = "a@example.com"
TOKEN = {"token": "access", "refresh_token": "refresh"}
CALENDAR_ID = "cal_user_a@group.calendar.google.com"


def _config() -> WebAuthConfig:
    return WebAuthConfig(
        client_config={"web": {"client_id": "cid"}},
        redirect_uri="https://app.test/auth/callback",
        session_secret="unit-test-session-secret",
        audience="cid",
        tester_allowlist=frozenset({EMAIL}),
        https_only=False,
    )


def _logged_in_client(monkeypatch: pytest.MonkeyPatch) -> tuple[TestClient, object]:
    _service, env, _clock = make_service()
    cipher = TokenCipher(TokenCipher.generate_key())
    client = TestClient(create_app(env=env, auth_config=_config(), token_cipher=cipher))

    # Connect-time seam: identity + dedicated-calendar provisioning, all faked.
    monkeypatch.setattr(
        routes_auth,
        "build_authorization_url",
        lambda *, client_config, redirect_uri, state: f"https://g.test/auth?state={state}",
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
        lambda service, *, summary, time_zone="UTC": CALENDAR_ID,
    )

    state = parse_qs(
        urlparse(client.get("/auth/login", follow_redirects=False).headers["location"]).query
    )["state"][0]
    assert client.get(f"/auth/callback?code=c&state={state}", follow_redirects=False).status_code == 307
    return client, env


def test_hosted_write_targets_the_users_dedicated_calendar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _env = _logged_in_client(monkeypatch)

    client.post(
        "/api/onboard",
        json={"user_profile": _canonical_profile().model_dump(mode="json"), "timezone": "UTC"},
    )
    assert client.post("/api/propose", json={}).json()["state"] == "awaiting_user_approval"
    client.post("/api/approve", json={})

    # Write-path seam: a real GoogleCalendarAdapter over one fake transport.
    transport = FakeGoogleTransport()
    monkeypatch.setattr(calendar_service, "build_service_from_token", lambda token_json: object())
    monkeypatch.setattr(calendar_service, "GoogleApiHttpTransport", lambda service: transport)

    dry = client.post("/api/write", json={"dry_run": True}).json()
    assert dry["dry_run"] is True
    assert dry["planned_event_count"] == len(PLAN_TASK_IDS)

    written = client.post("/api/write", json={}).json()
    assert written["state"] == "active_plan"
    assert sorted(written["written_task_ids"]) == sorted(PLAN_TASK_IDS)
    assert sorted(written["verified_task_ids"]) == sorted(PLAN_TASK_IDS)

    # Every event was inserted on THIS user's dedicated calendar, never another.
    inserts = [cal for (method, cal) in transport.calls if method == "insert_event"]
    assert inserts
    assert all(calendar_id == CALENDAR_ID for calendar_id in inserts)


def test_client_cannot_redirect_write_to_another_calendar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _env = _logged_in_client(monkeypatch)
    client.post(
        "/api/onboard",
        json={"user_profile": _canonical_profile().model_dump(mode="json"), "timezone": "UTC"},
    )
    client.post("/api/propose", json={})
    client.post("/api/approve", json={})

    transport = FakeGoogleTransport()
    monkeypatch.setattr(calendar_service, "build_service_from_token", lambda token_json: object())
    monkeypatch.setattr(calendar_service, "GoogleApiHttpTransport", lambda service: transport)

    # A client-supplied target_calendar_id is ignored: the write still lands on
    # the user's dedicated calendar (the body value is not trusted).
    written = client.post("/api/write", json={"target_calendar_id": "victim@group.calendar.google.com"}).json()
    assert written["state"] == "active_plan"
    inserts = [cal for (method, cal) in transport.calls if method == "insert_event"]
    assert inserts and all(calendar_id == CALENDAR_ID for calendar_id in inserts)


def test_build_user_calendar_service_requires_connection() -> None:
    _service, env, _clock = make_service()
    with pytest.raises(CycleError):
        build_user_calendar_service(
            env, user_id="never-connected", token_cipher=TokenCipher(TokenCipher.generate_key())
        )
