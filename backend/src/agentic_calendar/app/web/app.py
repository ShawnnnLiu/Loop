"""FastAPI application factory for the local/hosted web surface.

``create_app`` wires the cycle routes plus the exception handlers that map the
deterministic core's typed errors onto HTTP status codes. It runs in one of two
modes:

* **dev** (no ``auth_config``): the Increment-1 localhost surface — a single
  configured ``default_user_id``, no authentication.
* **hosted** (``auth_config`` supplied): signed-cookie sessions, the ``/auth``
  login flow, and a per-request ``user_id`` from the session. A
  ``token_cipher`` is required so the login callback can encrypt tokens at rest.

Either way every calendar mutation still flows through :class:`CycleService`,
so no axiom-06 invariant is relaxed for the web surface.

The user-facing product is the React SPA in ``frontend/`` (built to
``frontend/dist/``). When a built ``spa_dist`` is supplied, it is served as
static assets with an SPA-routing fallback: the client router owns the app
routes, and ``/api`` / ``/auth`` / ``/healthz`` are registered first so they
always win over the catch-all. The SPA is a thin client — every mutation is a
normal ``/api`` call subject to the same server checks, so it can never bypass
an axiom-06 invariant.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from starlette.middleware.sessions import SessionMiddleware

from agentic_calendar.app.cycle import CycleError, CycleService
from agentic_calendar.app.environment import AppEnvironment
from agentic_calendar.common.errors import AgenticCalendarError
from agentic_calendar.common.secrets import TokenCipher

from .config import WebAuthConfig
from .routes_auth import router as auth_router
from .routes_cycle import router as cycle_router


def default_spa_dist() -> Path:
    """The repo's built SPA directory (``frontend/dist``), relative to this file.

    Used by the composition roots (dev ``__main__`` and hosted ``server``) so a
    run from a repo checkout serves the SPA without configuration. Hosted deploys
    may override the location with ``SPA_DIST_DIR``."""
    return Path(__file__).resolve().parents[5] / "frontend" / "dist"


def default_landing_index() -> Path:
    """The repo's static landing page (``landing/index.html``), relative to here.

    The unauthenticated marketing entry served at ``/``; hosted deploys may
    override it with ``LANDING_INDEX``."""
    return Path(__file__).resolve().parents[5] / "landing" / "index.html"


def default_how_its_built() -> Path:
    """The repo's static engineering-story page (``landing/how-its-built.html``).

    Served at ``/how-its-built`` next to the landing — the no-sign-in
    architecture page recruiters land on. Hosted deploys may override it with
    ``HOW_ITS_BUILT_INDEX``."""
    return Path(__file__).resolve().parents[5] / "landing" / "how-its-built.html"


def default_sources_page() -> Path:
    """The repo's static sources / further-reading page (``landing/sources.html``).

    Served at ``/sources`` next to the landing — the crawlable bibliography of the
    grounding corpus (generated from ``backend/corpus/corpus.db``), linked from the
    homepage and footer. Hosted deploys may override it with ``SOURCES_INDEX``."""
    return Path(__file__).resolve().parents[5] / "landing" / "sources.html"


def default_privacy_page() -> Path:
    """The repo's static privacy-policy page (``landing/privacy.html``).

    Served at ``/privacy`` next to the landing — Google's OAuth verification
    requires it, linked from the homepage. Hosted deploys may override it with
    ``PRIVACY_INDEX``."""
    return Path(__file__).resolve().parents[5] / "landing" / "privacy.html"


def default_terms_page() -> Path:
    """The repo's static terms-of-service page (``landing/terms.html``).

    Served at ``/terms`` next to the landing. Hosted deploys may override it
    with ``TERMS_INDEX``."""
    return Path(__file__).resolve().parents[5] / "landing" / "terms.html"


# Every HTML document is served ``no-cache`` (store, but revalidate before
# reuse). Without it, browsers heuristically cache these responses, and a
# cached SPA shell squats on whatever URL served it: before /privacy shipped,
# the catch-all answered there with index.html, and browsers kept replaying it
# — client-redirecting /privacy into the app — long after the real page went
# live. Hashed ``/assets`` bundles are exempt; their names change per build.
_HTML_NO_CACHE = {"Cache-Control": "no-cache"}


def _mount_spa(app: FastAPI, dist_dir: Path) -> None:
    """Serve the built SPA: hashed bundles under ``/assets`` and ``index.html``
    as the fallback for every other GET, so the client router owns app routes
    (``/onboarding``, ``/today``, …). Registered last, after ``/api`` / ``/auth``
    / ``/healthz``, which therefore take precedence over this catch-all."""
    index = dist_dir / "index.html"
    assets = dist_dir / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.api_route("/{spa_path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    def spa(spa_path: str) -> FileResponse:
        # A real top-level static file (favicon, etc.) is served as-is, confined
        # to the dist dir; anything else is an SPA route -> hand back index.html.
        candidate = (dist_dir / spa_path).resolve()
        if spa_path and candidate.is_file() and candidate.is_relative_to(dist_dir.resolve()):
            return FileResponse(candidate)
        return FileResponse(index, headers=_HTML_NO_CACHE)


def _error_body(exc: Exception) -> dict[str, str]:
    body = {"error": str(exc), "type": exc.__class__.__name__}
    reason_code = getattr(exc, "reason_code", None)
    if reason_code is not None:
        # ReasonCode is a StrEnum; str() yields its wire value.
        body["reason_code"] = str(reason_code)
    return body


def create_app(
    *,
    env: AppEnvironment,
    auth_config: WebAuthConfig | None = None,
    token_cipher: TokenCipher | None = None,
    default_user_id: str | None = None,
    spa_dist: Path | None = None,
    landing_index: Path | None = None,
    how_its_built: Path | None = None,
    sources_page: Path | None = None,
    privacy_page: Path | None = None,
    terms_page: Path | None = None,
    canonical_host: str | None = None,
) -> FastAPI:
    """Build the app over a wired :class:`AppEnvironment`.

    Hosted mode needs ``auth_config`` + ``token_cipher``; dev mode needs
    ``default_user_id``. ``spa_dist`` (a built ``frontend/dist``) is served as
    the SPA when present; omit it (the default) for API-only test builds.
    ``landing_index`` (a static ``landing/index.html``) is served at ``/`` when
    present — the SPA then owns the app routes (the OAuth callback lands users on
    ``/app``), so the marketing root and the app don't fight over ``/``.
    ``canonical_host`` (a bare hostname) 301-redirects requests arriving under
    any other host — e.g. the old ``<app>.fly.dev`` name after a custom-domain
    cutover — to the same path on the canonical domain; unset means no redirect.
    """
    if auth_config is not None and token_cipher is None:
        raise ValueError("hosted mode (auth_config) requires a token_cipher")
    if auth_config is None and default_user_id is None:
        raise ValueError("dev mode requires default_user_id")

    app = FastAPI(title="Agentic Calendar", version="0.1.0")
    app.state.env = env
    app.state.cycle_service = CycleService(env)
    app.state.auth_enabled = auth_config is not None
    app.state.auth_config = auth_config
    app.state.token_cipher = token_cipher
    app.state.default_user_id = default_user_id

    if auth_config is not None:
        app.add_middleware(
            SessionMiddleware,
            secret_key=auth_config.session_secret,
            same_site="lax",
            https_only=auth_config.https_only,
        )
        app.include_router(auth_router)

    # Canonical-host redirect (custom-domain cutover): requests that arrive
    # under any other host — e.g. the retired <app>.fly.dev name — get a
    # path-and-query-preserving 301 to the canonical domain. Added after
    # SessionMiddleware so it runs outermost (redirect before any session
    # work). ``/healthz`` is exempt so machine probes never chase a redirect.
    normalized_canonical = (canonical_host or "").strip().lower()
    if normalized_canonical:

        @app.middleware("http")
        async def _canonical_host_redirect(
            request: Request, call_next: Callable[[Request], Awaitable[Response]]
        ) -> Response:
            host = (request.url.hostname or "").lower()
            if host and host != normalized_canonical and request.url.path != "/healthz":
                target = request.url.replace(scheme="https", netloc=normalized_canonical)
                return RedirectResponse(str(target), status_code=301)
            return await call_next(request)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    # Command-precondition failure (wrong state, missing record): the command
    # was not applicable. 409 Conflict — distinct from a bad request body.
    @app.exception_handler(CycleError)
    def _on_cycle_error(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(status_code=409, content=_error_body(exc))

    # Any other typed core error (e.g. a dedicated-calendar guard) that escapes
    # as an exception rather than a typed result.
    @app.exception_handler(AgenticCalendarError)
    def _on_core_error(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(status_code=400, content=_error_body(exc))

    # Invalid onboarding/contract payload from the client.
    @app.exception_handler(ValidationError)
    def _on_validation_error(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(status_code=422, content=_error_body(exc))

    # ValueError that is not a pydantic ValidationError (e.g. an unknown enum
    # value); pydantic's ValidationError is a ValueError subclass and is caught
    # by the more specific handler above.
    @app.exception_handler(ValueError)
    def _on_value_error(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(status_code=400, content=_error_body(exc))

    app.include_router(cycle_router)

    # The static landing owns "/" (registered before the SPA catch-all so it
    # wins there). The app routes belong to the SPA; the OAuth callback lands a
    # signed-in user on "/app", never here, so there is no session-conditional
    # rendering at "/".
    #
    # Every public HTML route accepts HEAD alongside GET: FastAPI's ``.get``
    # alone answers HEAD with 405, and automated link checkers — including
    # Google's OAuth-verification homepage probe — read that as an unreachable
    # page. FileResponse natively answers HEAD with headers only.
    if landing_index is not None and landing_index.is_file():

        @app.api_route("/", methods=["GET", "HEAD"], include_in_schema=False)
        def landing() -> FileResponse:
            return FileResponse(landing_index, headers=_HTML_NO_CACHE)

    # The static engineering-story page, a sibling of the landing. Like the
    # landing it must be registered before the SPA catch-all or the catch-all
    # would swallow the route.
    if how_its_built is not None and how_its_built.is_file():

        @app.api_route("/how-its-built", methods=["GET", "HEAD"], include_in_schema=False)
        def how_its_built_page() -> FileResponse:
            return FileResponse(how_its_built, headers=_HTML_NO_CACHE)

    # The static sources / further-reading page, a landing sibling: the crawlable
    # bibliography of the grounding corpus, linked from the homepage and footer.
    # Registered before the SPA catch-all so the catch-all can't swallow it.
    if sources_page is not None and sources_page.is_file():

        @app.api_route("/sources", methods=["GET", "HEAD"], include_in_schema=False)
        def sources() -> FileResponse:
            return FileResponse(sources_page, headers=_HTML_NO_CACHE)

    # robots.txt and sitemap.xml: SEO essentials built from the request's own
    # origin, so they stay correct under any host (and behind the canonical-host
    # 301). Registered unconditionally, before the SPA catch-all.
    _PUBLIC_PATHS = ("/", "/how-its-built", "/sources", "/privacy", "/terms")

    @app.api_route("/robots.txt", methods=["GET", "HEAD"], include_in_schema=False)
    def robots(request: Request) -> Response:
        base = str(request.base_url).rstrip("/")
        body = f"User-agent: *\nAllow: /\nSitemap: {base}/sitemap.xml\n"
        return Response(content=body, media_type="text/plain")

    @app.api_route("/sitemap.xml", methods=["GET", "HEAD"], include_in_schema=False)
    def sitemap(request: Request) -> Response:
        base = str(request.base_url).rstrip("/")
        urls = "".join(f"  <url><loc>{base}{p}</loc></url>\n" for p in _PUBLIC_PATHS)
        body = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            f"{urls}</urlset>\n"
        )
        return Response(content=body, media_type="application/xml")

    # The static policy pages (/privacy, /terms), landing siblings. /privacy is
    # a Google OAuth verification requirement (linked from the homepage). Like
    # the landing they must be registered before the SPA catch-all.
    if privacy_page is not None and privacy_page.is_file():

        @app.api_route("/privacy", methods=["GET", "HEAD"], include_in_schema=False)
        def privacy() -> FileResponse:
            return FileResponse(privacy_page, headers=_HTML_NO_CACHE)

    if terms_page is not None and terms_page.is_file():

        @app.api_route("/terms", methods=["GET", "HEAD"], include_in_schema=False)
        def terms() -> FileResponse:
            return FileResponse(terms_page, headers=_HTML_NO_CACHE)

    # The SPA fallback is registered LAST so its catch-all never shadows the API,
    # auth, health, or landing routes above. Only mounted when a real build is
    # present, so API-only test builds (no dist) keep a clean 404 on non-API paths.
    if spa_dist is not None and (spa_dist / "index.html").is_file():
        _mount_spa(app, spa_dist)
    return app
