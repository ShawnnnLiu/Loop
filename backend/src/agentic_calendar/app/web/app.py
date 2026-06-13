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
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.middleware.sessions import SessionMiddleware

from agentic_calendar.app.cycle import CycleError, CycleService
from agentic_calendar.app.environment import AppEnvironment
from agentic_calendar.common.errors import AgenticCalendarError
from agentic_calendar.common.secrets import TokenCipher

from .config import WebAuthConfig
from .pages import router as pages_router
from .routes_auth import router as auth_router
from .routes_cycle import router as cycle_router


def _error_body(exc: Exception) -> dict[str, str]:
    return {"error": str(exc), "type": exc.__class__.__name__}


def create_app(
    *,
    env: AppEnvironment,
    auth_config: WebAuthConfig | None = None,
    token_cipher: TokenCipher | None = None,
    default_user_id: str | None = None,
) -> FastAPI:
    """Build the app over a wired :class:`AppEnvironment`.

    Hosted mode needs ``auth_config`` + ``token_cipher``; dev mode needs
    ``default_user_id``.
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
        app.include_router(pages_router)

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
    return app
