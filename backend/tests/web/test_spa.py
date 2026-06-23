"""The built-SPA static surface (F-H cutover).

``create_app(spa_dist=...)`` serves the React build as static assets with an
SPA-routing fallback: ``index.html`` for any app route, hashed bundles under
``/assets``, and — critically — the ``/api`` / ``/healthz`` routes still win
over the catch-all. A temp ``dist`` stands in for a real ``frontend/dist`` so
the test is deterministic whether or not the frontend has been built.
"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from agentic_calendar.app.web.app import create_app
from tests.app.test_cycle import USER_ID, make_service

_INDEX_HTML = "<!doctype html><title>Loop</title><div id=root></div>"
_ASSET_JS = "console.log('loop')"


def _dist(tmp_path: Path) -> Path:
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text(_INDEX_HTML)
    (dist / "assets" / "index-abc123.js").write_text(_ASSET_JS)
    (dist / "favicon.svg").write_text("<svg/>")
    return dist


def _client(tmp_path: Path) -> TestClient:
    _service, env, _clock = make_service()
    return TestClient(create_app(env=env, default_user_id=USER_ID, spa_dist=_dist(tmp_path)))


def test_root_serves_the_spa_index(tmp_path: Path) -> None:
    resp = _client(tmp_path).get("/")
    assert resp.status_code == 200
    assert _INDEX_HTML in resp.text


def test_client_route_falls_back_to_index(tmp_path: Path) -> None:
    # A deep app route the client router owns (e.g. /today, /approve) is unknown
    # to the server; it must serve index.html so the SPA boots and routes itself.
    client = _client(tmp_path)
    for route in ("/today", "/approve", "/onboarding/deep/link"):
        resp = client.get(route)
        assert resp.status_code == 200, route
        assert _INDEX_HTML in resp.text


def test_hashed_asset_is_served(tmp_path: Path) -> None:
    resp = _client(tmp_path).get("/assets/index-abc123.js")
    assert resp.status_code == 200
    assert _ASSET_JS in resp.text


def test_top_level_static_file_is_served(tmp_path: Path) -> None:
    resp = _client(tmp_path).get("/favicon.svg")
    assert resp.status_code == 200
    assert resp.text == "<svg/>"


def test_api_and_health_win_over_the_spa_catch_all(tmp_path: Path) -> None:
    client = _client(tmp_path)
    # The catch-all is registered last, so the real routes still resolve.
    assert client.get("/healthz").json() == {"status": "ok"}
    status = client.get("/api/status")
    assert status.status_code == 200
    assert status.json()["user_id"] == USER_ID


def test_no_dist_means_no_spa_mount() -> None:
    # Omitting spa_dist (the API-only test build) leaves non-API GETs at 404 —
    # the catch-all is never registered.
    _service, env, _clock = make_service()
    client = TestClient(create_app(env=env, default_user_id=USER_ID))
    assert client.get("/", follow_redirects=False).status_code == 404
    assert client.get("/today", follow_redirects=False).status_code == 404
    assert client.get("/healthz").status_code == 200
