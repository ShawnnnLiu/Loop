"""Canonical-host redirect (recruiter-readiness 02: domain cutover).

``create_app(canonical_host=...)`` permanently redirects any request whose
host differs from the configured canonical domain — e.g. the old
``<app>.fly.dev`` name after a custom-domain cutover — to the same path and
query on the canonical host. Unset (every dev/test composition today) it is a
strict no-op. ``/healthz`` is exempt so machine probes never chase a redirect.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from agentic_calendar.app.web.app import create_app
from tests.app.test_cycle import USER_ID, make_service

OLD_BASE = "http://acme-agentic-cal.fly.dev"
NEW_HOST = "loop.example.dev"


def _client(canonical_host: str | None, base_url: str = OLD_BASE) -> TestClient:
    _service, env, _clock = make_service()
    app = create_app(env=env, default_user_id=USER_ID, canonical_host=canonical_host)
    return TestClient(app, base_url=base_url)


def test_unset_canonical_host_is_a_no_op() -> None:
    client = _client(None)
    assert client.get("/healthz", follow_redirects=False).status_code == 200
    assert client.get("/api/status", follow_redirects=False).status_code == 200


def test_old_host_gets_path_and_query_preserving_301() -> None:
    resp = _client(NEW_HOST).get("/app/today?tab=week", follow_redirects=False)
    assert resp.status_code == 301
    assert resp.headers["location"] == f"https://{NEW_HOST}/app/today?tab=week"


def test_canonical_host_is_served_directly() -> None:
    client = _client(NEW_HOST, base_url=f"https://{NEW_HOST}")
    assert client.get("/api/status", follow_redirects=False).status_code == 200


def test_healthz_is_exempt_on_the_old_host() -> None:
    resp = _client(NEW_HOST).get("/healthz", follow_redirects=False)
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
