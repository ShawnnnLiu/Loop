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

from agentic_calendar.app.web.app import create_app, default_privacy_page, default_terms_page
from tests.app.test_cycle import USER_ID, make_service

_INDEX_HTML = "<!doctype html><title>Loop</title><div id=root></div>"
_ASSET_JS = "console.log('loop')"
_LANDING_HTML = "<!doctype html><title>Loop — landing</title><h1>LANDING_MARKER</h1>"
_BUILT_HTML = "<!doctype html><title>Loop — how its built</title><h1>BUILT_MARKER</h1>"
_PRIVACY_HTML = "<!doctype html><title>Loop — privacy</title><h1>PRIVACY_MARKER</h1>"
_TERMS_HTML = "<!doctype html><title>Loop — terms</title><h1>TERMS_MARKER</h1>"


def _dist(tmp_path: Path) -> Path:
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text(_INDEX_HTML)
    (dist / "assets" / "index-abc123.js").write_text(_ASSET_JS)
    (dist / "favicon.svg").write_text("<svg/>")
    return dist


def _landing(tmp_path: Path) -> Path:
    index = tmp_path / "landing" / "index.html"
    index.parent.mkdir(parents=True)
    index.write_text(_LANDING_HTML)
    return index


def _how_its_built(tmp_path: Path) -> Path:
    page = tmp_path / "landing" / "how-its-built.html"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(_BUILT_HTML)
    return page


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


# --------------------------------------------------------------------------- #
# Landing (L-B): the static marketing page owns "/", the SPA owns app routes.
# --------------------------------------------------------------------------- #


def test_landing_owns_root_and_spa_owns_app_routes(tmp_path: Path) -> None:
    _service, env, _clock = make_service()
    client = TestClient(
        create_app(
            env=env,
            default_user_id=USER_ID,
            spa_dist=_dist(tmp_path),
            landing_index=_landing(tmp_path),
        )
    )
    # "/" serves the landing, NOT the SPA index — the explicit route wins over
    # the SPA catch-all.
    root = client.get("/")
    assert root.status_code == 200
    assert "LANDING_MARKER" in root.text
    assert _INDEX_HTML not in root.text
    # App routes (incl. the /app entry the OAuth callback lands on) still serve
    # the SPA so the client router boots.
    for route in ("/app", "/today", "/onboarding"):
        resp = client.get(route)
        assert resp.status_code == 200, route
        assert _INDEX_HTML in resp.text
    # The API still wins over both.
    assert client.get("/api/status").json()["user_id"] == USER_ID


def test_landing_served_without_a_spa_build(tmp_path: Path) -> None:
    # Landing present but no SPA build: "/" is the landing, app routes 404.
    _service, env, _clock = make_service()
    client = TestClient(
        create_app(env=env, default_user_id=USER_ID, landing_index=_landing(tmp_path))
    )
    assert "LANDING_MARKER" in client.get("/").text
    assert client.get("/today", follow_redirects=False).status_code == 404


# --------------------------------------------------------------------------- #
# How it's built (recruiter-readiness 03): a second static page at
# /how-its-built, registered before the SPA catch-all so it isn't swallowed.
# --------------------------------------------------------------------------- #


def test_how_its_built_wins_over_the_spa_catch_all(tmp_path: Path) -> None:
    _service, env, _clock = make_service()
    client = TestClient(
        create_app(
            env=env,
            default_user_id=USER_ID,
            spa_dist=_dist(tmp_path),
            landing_index=_landing(tmp_path),
            how_its_built=_how_its_built(tmp_path),
        )
    )
    built = client.get("/how-its-built")
    assert built.status_code == 200
    assert "BUILT_MARKER" in built.text
    assert _INDEX_HTML not in built.text
    # The landing and the SPA are unaffected by the extra static route.
    assert "LANDING_MARKER" in client.get("/").text
    for route in ("/app", "/today"):
        resp = client.get(route)
        assert resp.status_code == 200, route
        assert _INDEX_HTML in resp.text


def test_missing_how_its_built_file_leaves_route_to_the_spa(tmp_path: Path) -> None:
    # Point at a nonexistent file: the route must not be registered, so the
    # SPA catch-all serves /how-its-built like any other unknown path.
    _service, env, _clock = make_service()
    client = TestClient(
        create_app(
            env=env,
            default_user_id=USER_ID,
            spa_dist=_dist(tmp_path),
            how_its_built=tmp_path / "landing" / "missing.html",
        )
    )
    resp = client.get("/how-its-built")
    assert resp.status_code == 200
    assert _INDEX_HTML in resp.text


# --------------------------------------------------------------------------- #
# Policy pages (publication-requirements 03 §2): /privacy and /terms, landing
# siblings registered before the SPA catch-all. /privacy is a Google OAuth
# verification requirement.
# --------------------------------------------------------------------------- #


def _policy_page(tmp_path: Path, name: str, html: str) -> Path:
    page = tmp_path / "landing" / name
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(html)
    return page


def test_policy_pages_win_over_the_spa_catch_all(tmp_path: Path) -> None:
    _service, env, _clock = make_service()
    client = TestClient(
        create_app(
            env=env,
            default_user_id=USER_ID,
            spa_dist=_dist(tmp_path),
            landing_index=_landing(tmp_path),
            privacy_page=_policy_page(tmp_path, "privacy.html", _PRIVACY_HTML),
            terms_page=_policy_page(tmp_path, "terms.html", _TERMS_HTML),
        )
    )
    for route, marker in (("/privacy", "PRIVACY_MARKER"), ("/terms", "TERMS_MARKER")):
        resp = client.get(route)
        assert resp.status_code == 200, route
        assert marker in resp.text
        assert _INDEX_HTML not in resp.text
    # The landing and the SPA are unaffected by the extra static routes.
    assert "LANDING_MARKER" in client.get("/").text
    assert _INDEX_HTML in client.get("/today").text


def test_missing_policy_files_leave_routes_to_the_spa(tmp_path: Path) -> None:
    _service, env, _clock = make_service()
    client = TestClient(
        create_app(
            env=env,
            default_user_id=USER_ID,
            spa_dist=_dist(tmp_path),
            privacy_page=tmp_path / "landing" / "missing-privacy.html",
            terms_page=tmp_path / "landing" / "missing-terms.html",
        )
    )
    for route in ("/privacy", "/terms"):
        resp = client.get(route)
        assert resp.status_code == 200, route
        assert _INDEX_HTML in resp.text


def test_html_documents_are_served_no_cache(tmp_path: Path) -> None:
    # Every HTML document must carry Cache-Control: no-cache so browsers
    # revalidate instead of replaying a stale copy. The trap this pins: before
    # /privacy shipped, the SPA catch-all answered there with index.html;
    # browsers heuristically cached it and kept client-redirecting /privacy
    # into the app after the real page went live.
    _service, env, _clock = make_service()
    client = TestClient(
        create_app(
            env=env,
            default_user_id=USER_ID,
            spa_dist=_dist(tmp_path),
            landing_index=_landing(tmp_path),
            how_its_built=_how_its_built(tmp_path),
            privacy_page=_policy_page(tmp_path, "privacy.html", _PRIVACY_HTML),
            terms_page=_policy_page(tmp_path, "terms.html", _TERMS_HTML),
        )
    )
    for route in ("/", "/how-its-built", "/privacy", "/terms", "/app", "/today"):
        resp = client.get(route)
        assert resp.status_code == 200, route
        assert resp.headers.get("cache-control") == "no-cache", route
    # Hashed bundles stay cache-friendly: no no-cache header on /assets.
    asset = client.get("/assets/index-abc123.js")
    assert asset.status_code == 200
    assert "cache-control" not in asset.headers


def test_in_repo_policy_pages_have_the_required_content() -> None:
    # Serve the real committed landing/privacy.html + terms.html and check the
    # content the OAuth-verification spec requires is actually present.
    _service, env, _clock = make_service()
    client = TestClient(
        create_app(
            env=env,
            default_user_id=USER_ID,
            privacy_page=default_privacy_page(),
            terms_page=default_terms_page(),
        )
    )
    privacy = client.get("/privacy")
    assert privacy.status_code == 200
    assert privacy.headers["content-type"].startswith("text/html")
    for required in (
        "Privacy Policy",
        "July 19, 2026",
        "1732003904liu@gmail.com",
        # The explicit negative claim about the freebusy scope.
        "not readable",
        # The compliance anchor.
        "Google API Services User Data Policy",
        "Limited Use",
        # The LLM boundary, stated accurately (verified against the
        # prompt-exposure table: no Google calendar data reaches prompts).
        "Google Calendar data does not",
        # Revoke + email-to-delete are the only user controls today.
        "myaccount.google.com/permissions",
        # Product/ops metrics collection (users, acceptance, latency, cost,
        # repair, completion) is disclosed, with the aggregates-only claim.
        "Service metrics",
        "aggregates across users",
    ):
        assert required in privacy.text, required

    terms = client.get("/terms")
    assert terms.status_code == 200
    assert terms.headers["content-type"].startswith("text/html")
    for required in (
        "Terms of Service",
        "July 19, 2026",
        "as is",
        "no uptime guarantee",
        "1732003904liu@gmail.com",
        "Service metrics",
    ):
        assert required in terms.text, required
