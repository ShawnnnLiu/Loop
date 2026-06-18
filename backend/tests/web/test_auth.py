"""Tests for the hosted-mode session auth + Google sign-in flow.

The Google handshake is faked at the ``routes_auth`` seam (the names it
imported), so no network call happens. ``TestClient`` persists the signed
session cookie across requests, so the real ``state`` round-trip and the
session-derived ``user_id`` are exercised end to end.
"""

from __future__ import annotations

import json
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

from agentic_calendar.app.environment import AppEnvironment
from agentic_calendar.app.web import routes_auth
from agentic_calendar.app.web.app import create_app
from agentic_calendar.app.web.config import WebAuthConfig
from agentic_calendar.app.web.routes_auth import _user_id_for_sub
from agentic_calendar.common.secrets import TokenCipher
from agentic_calendar.tools.google_oauth_web import GoogleIdentity
from tests.app.test_cycle import make_service

SUB = "google-sub-123"
EMAIL = "tester@example.com"
TOKEN = {"token": "access", "refresh_token": "refresh", "id_token": "jwt"}


def _config() -> WebAuthConfig:
    return WebAuthConfig(
        client_config={"web": {"client_id": "cid"}},
        redirect_uri="https://app.test/auth/callback",
        session_secret="unit-test-session-secret",
        audience="cid",
        tester_allowlist=frozenset({EMAIL}),
        https_only=False,  # TestClient speaks http
    )


def _app() -> tuple[TestClient, AppEnvironment, TokenCipher]:
    _service, env, _clock = make_service()
    cipher = TokenCipher(TokenCipher.generate_key())
    app = create_app(env=env, auth_config=_config(), token_cipher=cipher)
    return TestClient(app), env, cipher


def _login(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> str:
    """Drive /auth/login; return the CSRF state the route minted."""
    monkeypatch.setattr(
        routes_auth,
        "build_authorization_url",
        lambda *, client_config, redirect_uri, state: (
            f"https://accounts.google.test/o/oauth2/auth?state={state}",
            "test-verifier",
        ),
    )
    resp = client.get("/auth/login", follow_redirects=False)
    assert resp.status_code == 307
    return parse_qs(urlparse(resp.headers["location"]).query)["state"][0]


def _complete_login(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    *,
    sub: str = SUB,
    email: str = EMAIL,
) -> object:
    state = _login(client, monkeypatch)
    monkeypatch.setattr(routes_auth, "exchange_code", lambda **kwargs: dict(TOKEN))
    monkeypatch.setattr(
        routes_auth,
        "identity_from_token",
        lambda token_json, *, audience: GoogleIdentity(sub=sub, email=email),
    )
    # Connect-time dedicated-calendar provisioning (faked SDK seam).
    monkeypatch.setattr(routes_auth, "build_service_from_token", lambda token_json: object())
    monkeypatch.setattr(
        routes_auth,
        "create_dedicated_calendar",
        lambda service, *, summary, time_zone="UTC": "cal_provisioned",
    )
    return client.get(f"/auth/callback?code=abc&state={state}", follow_redirects=False)


def test_login_redirects_to_consent(monkeypatch: pytest.MonkeyPatch) -> None:
    client, _env, _cipher = _app()
    state = _login(client, monkeypatch)
    assert state  # a non-empty CSRF token was minted and round-tripped


def test_unauthenticated_request_is_401() -> None:
    client, _env, _cipher = _app()
    assert client.get("/api/status").status_code == 401


def test_full_login_authenticates_and_persists_encrypted_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, env, cipher = _app()
    resp = _complete_login(client, monkeypatch)
    assert resp.status_code == 307
    assert resp.headers["location"] == "/"

    user_id = _user_id_for_sub(SUB)
    status = client.get("/api/status")
    assert status.status_code == 200
    assert status.json()["user_id"] == user_id

    record = env.credential_store.get_by_user(user_id)
    assert record is not None
    assert record.email == EMAIL
    assert record.dedicated_calendar_id == "cal_provisioned"  # provisioned on connect
    # Stored ciphertext is not the plaintext token, but decrypts back to it.
    assert record.encrypted_token != json.dumps(TOKEN)
    assert json.loads(cipher.decrypt(record.encrypted_token)) == TOKEN


def test_callback_rejects_mismatched_state(monkeypatch: pytest.MonkeyPatch) -> None:
    client, _env, _cipher = _app()
    _login(client, monkeypatch)
    monkeypatch.setattr(routes_auth, "exchange_code", lambda **kwargs: dict(TOKEN))
    monkeypatch.setattr(
        routes_auth,
        "identity_from_token",
        lambda token_json, *, audience: GoogleIdentity(sub=SUB, email=EMAIL),
    )
    resp = client.get("/auth/callback?code=abc&state=forged", follow_redirects=False)
    assert resp.status_code == 400


def test_callback_rejects_non_allowlisted_email(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, env, _cipher = _app()
    resp = _complete_login(client, monkeypatch, email="intruder@example.com")
    assert resp.status_code == 403
    # No credential persisted, and the request stays unauthenticated.
    assert env.credential_store.get_user_id_for_sub(SUB) is None
    assert client.get("/api/status").status_code == 401


def test_logout_clears_session(monkeypatch: pytest.MonkeyPatch) -> None:
    client, _env, _cipher = _app()
    _complete_login(client, monkeypatch)
    assert client.get("/api/status").status_code == 200
    assert client.post("/auth/logout").status_code == 200
    assert client.get("/api/status").status_code == 401


def test_returning_user_keeps_id_and_dedicated_calendar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, env, _cipher = _app()
    _complete_login(client, monkeypatch)
    user_id = _user_id_for_sub(SUB)

    # Simulate Increment 4 attaching a dedicated calendar (rebuild + save).
    record = env.credential_store.get_by_user(user_id)
    assert record is not None
    env.credential_store.save(
        record.model_validate(
            record.model_dump() | {"dedicated_calendar_id": "cal_existing"}
        )
    )

    # A second sign-in with the same Google sub resolves to the same user and
    # preserves the dedicated calendar id.
    client.post("/auth/logout")
    _complete_login(client, monkeypatch)
    again = env.credential_store.get_by_user(user_id)
    assert again is not None
    assert again.dedicated_calendar_id == "cal_existing"
    assert env.credential_store.get_user_id_for_sub(SUB) == user_id
