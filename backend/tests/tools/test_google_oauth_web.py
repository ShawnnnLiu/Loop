"""Tests for the web OAuth handshake helpers.

The Google SDK is faked at the seam — exactly the recorded-transport pattern
the adapter tests use — so no network call happens in CI. The functions do
function-local SDK imports, so patching the SDK attribute by its dotted path
before the call takes effect.
"""

from __future__ import annotations

import json
import os

import pytest

from agentic_calendar.tools.google_oauth_web import (
    WEB_SCOPES,
    GoogleIdentity,
    GoogleOAuthError,
    build_authorization_url,
    build_service_from_token,
    create_dedicated_calendar,
    exchange_code,
    identity_from_token,
)


class _FakeCreds:
    id_token = "fake.jwt.token"

    def to_json(self) -> str:
        return json.dumps(
            {
                "token": "access-token",
                "refresh_token": "refresh-token",
                "client_id": "client-id",
                "client_secret": "client-secret",
                "scopes": list(WEB_SCOPES),
            }
        )


class _FakeFlow:
    def __init__(self) -> None:
        self.credentials = _FakeCreds()
        self.code_verifier = "test-verifier"

    @classmethod
    def from_client_config(cls, config, scopes, redirect_uri, state=None):  # type: ignore[no-untyped-def]
        return cls()

    def authorization_url(self, **kwargs):  # type: ignore[no-untyped-def]
        state = kwargs.get("state")
        return (f"https://accounts.google.com/o/oauth2/auth?state={state}", state)

    def fetch_token(self, code):  # type: ignore[no-untyped-def]
        self._code = code


def test_build_authorization_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("google_auth_oauthlib.flow.Flow", _FakeFlow)
    url, code_verifier = build_authorization_url(
        client_config={"web": {}}, redirect_uri="https://app.test/auth/callback", state="st123"
    )
    assert "state=st123" in url
    assert code_verifier == "test-verifier"  # PKCE verifier returned for the session


def test_exchange_code_relaxes_oauthlib_scope_check(monkeypatch: pytest.MonkeyPatch) -> None:
    # Google returns a reordered superset of scopes (incremental auth); the
    # exchange must relax oauthlib's strict scope-equality check.
    monkeypatch.delenv("OAUTHLIB_RELAX_TOKEN_SCOPE", raising=False)
    monkeypatch.setattr("google_auth_oauthlib.flow.Flow", _FakeFlow)
    exchange_code(
        client_config={"web": {}},
        redirect_uri="https://app.test/auth/callback",
        code="auth-code",
        state="st",
    )
    assert "OAUTHLIB_RELAX_TOKEN_SCOPE" in os.environ


def test_exchange_code_translates_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FailingFlow(_FakeFlow):
        def fetch_token(self, code):  # type: ignore[no-untyped-def]
            raise RuntimeError("invalid_grant: missing code verifier")

    monkeypatch.setattr("google_auth_oauthlib.flow.Flow", _FailingFlow)
    with pytest.raises(GoogleOAuthError):
        exchange_code(
            client_config={"web": {}},
            redirect_uri="https://app.test/auth/callback",
            code="bad",
            state="st",
        )


def test_exchange_code_includes_id_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("google_auth_oauthlib.flow.Flow", _FakeFlow)
    token = exchange_code(
        client_config={"web": {}},
        redirect_uri="https://app.test/auth/callback",
        code="auth-code",
        state="st",
    )
    assert token["refresh_token"] == "refresh-token"
    # to_json() omitted id_token; the helper backfills it from creds.id_token.
    assert token["id_token"] == "fake.jwt.token"


def test_identity_from_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "google.oauth2.id_token.verify_oauth2_token",
        lambda raw, request, audience: {"sub": "S1", "email": "u@example.com"},
    )
    identity = identity_from_token({"id_token": "jwt"}, audience="client-id")
    assert identity == GoogleIdentity(sub="S1", email="u@example.com")


def test_identity_from_token_without_id_token() -> None:
    with pytest.raises(GoogleOAuthError):
        identity_from_token({}, audience="client-id")


def test_identity_from_token_missing_claims(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "google.oauth2.id_token.verify_oauth2_token",
        lambda raw, request, audience: {"sub": "S1"},  # no email
    )
    with pytest.raises(GoogleOAuthError):
        identity_from_token({"id_token": "jwt"}, audience="client-id")


def test_build_service_from_token(monkeypatch: pytest.MonkeyPatch) -> None:
    sentinel = object()
    monkeypatch.setattr(
        "google.oauth2.credentials.Credentials.from_authorized_user_info",
        lambda info, scopes: object(),
    )
    monkeypatch.setattr("googleapiclient.discovery.build", lambda *a, **k: sentinel)
    service = build_service_from_token(
        {"token": "t", "refresh_token": "r", "client_id": "c", "client_secret": "s"}
    )
    assert service is sentinel


class _FakeCalendars:
    def insert(self, body):  # type: ignore[no-untyped-def]
        self._body = body
        return self

    def execute(self):  # type: ignore[no-untyped-def]
        return {"id": "cal_new@group.calendar.google.com"}


class _FakeService:
    def calendars(self):  # type: ignore[no-untyped-def]
        return _FakeCalendars()


def test_create_dedicated_calendar() -> None:
    calendar_id = create_dedicated_calendar(
        _FakeService(), summary="Agentic Calendar - user_1"
    )
    assert calendar_id == "cal_new@group.calendar.google.com"
