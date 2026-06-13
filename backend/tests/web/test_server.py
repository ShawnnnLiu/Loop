"""Tests for the hosted entrypoint's environment wiring.

These build the real hosted app over a temp SQLite file and a fake client
secret, then exercise only the no-LLM surface (health, login page, the
unauthenticated 401). A dummy ``ANTHROPIC_API_KEY`` lets the live node bundle
construct without any network call.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agentic_calendar.app.web.config import WebConfigError
from agentic_calendar.app.web.server import create_hosted_app
from agentic_calendar.common.secrets import TokenCipher

_CLIENT_JSON = {
    "web": {
        "client_id": "cid",
        "client_secret": "sec",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
}


def _set_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    secret_file = tmp_path / "client.json"
    secret_file.write_text(json.dumps(_CLIENT_JSON))
    monkeypatch.setenv("SHARED_DB_PATH", str(tmp_path / "app.db"))
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET_FILE", str(secret_file))
    monkeypatch.setenv("OAUTH_REDIRECT_URI", "https://app.test/auth/callback")
    monkeypatch.setenv("APP_SESSION_SECRET", "session-secret")
    monkeypatch.setenv("APP_TOKEN_ENCRYPTION_KEY", TokenCipher.generate_key())
    monkeypatch.setenv("TESTER_ALLOWLIST", "a@example.com, b@example.com")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "dummy-key-no-network")
    monkeypatch.setenv("APP_HTTPS_ONLY", "0")


def test_create_hosted_app_wires_from_env(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _set_env(monkeypatch, tmp_path)
    client = TestClient(create_hosted_app())

    assert client.get("/healthz").json() == {"status": "ok"}
    login = client.get("/")
    assert login.status_code == 200
    assert "Connect Google Calendar" in login.text
    # Hosted mode: the API is session-gated.
    assert client.get("/api/status").status_code == 401


def test_create_hosted_app_requires_db_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _set_env(monkeypatch, tmp_path)
    monkeypatch.delenv("SHARED_DB_PATH")
    with pytest.raises(WebConfigError):
        create_hosted_app()


def test_create_hosted_app_requires_oauth_config(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _set_env(monkeypatch, tmp_path)
    monkeypatch.delenv("TESTER_ALLOWLIST")
    with pytest.raises(WebConfigError):
        create_hosted_app()
