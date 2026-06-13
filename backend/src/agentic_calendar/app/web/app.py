"""FastAPI application factory for the local web surface (F0a).

``create_app`` is pure dependency injection: hand it a fully wired
:class:`CycleService` and the single acting user id, and it mounts the cycle
routes plus the exception handlers that map the deterministic core's typed
errors onto HTTP status codes. Tests inject a fixture-backed service; the
``python -m agentic_calendar.app.web`` entrypoint injects the offline demo
service (see ``__main__``).
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from agentic_calendar.app.cycle import CycleError, CycleService
from agentic_calendar.common.errors import AgenticCalendarError

from .routes_cycle import router as cycle_router


def _error_body(exc: Exception) -> dict[str, str]:
    return {"error": str(exc), "type": exc.__class__.__name__}


def create_app(cycle_service: CycleService, *, default_user_id: str) -> FastAPI:
    """Build the app over an already-wired cycle service.

    ``default_user_id`` is the single acting user for this Increment-1 surface
    (no auth yet); :func:`agentic_calendar.app.web.deps.require_user` reads it
    back off ``app.state``.
    """
    app = FastAPI(title="Agentic Calendar (local)", version="0.1.0")
    app.state.cycle_service = cycle_service
    app.state.default_user_id = default_user_id

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
