"""FastAPI request dependencies: resolve the cycle service and the acting user.

:func:`require_user` is the trust boundary. In hosted mode (a
:class:`~agentic_calendar.app.web.config.WebAuthConfig` was supplied) the acting
``user_id`` is read from the signed session cookie and a missing session is a
401 — it is never taken from the request body, query, or path. In the
Increment-1 localhost dev mode (no auth) it returns the single configured id.

Increment 4 swaps :func:`get_cycle_service` for a per-user build over that
user's stored Google credentials; routes depend on these names so that change
touches only this file.
"""

from __future__ import annotations

from typing import cast

from fastapi import HTTPException, Request

from agentic_calendar.app.cycle import CycleService


def get_cycle_service(request: Request) -> CycleService:
    """The cycle service wired at app startup (see ``app.state.cycle_service``)."""
    return cast(CycleService, request.app.state.cycle_service)


def require_user(request: Request) -> str:
    """The acting user id, resolved server-side.

    Hosted mode: from ``request.session["user_id"]`` (401 if unauthenticated).
    Dev mode: the single configured ``app.state.default_user_id``.
    """
    if request.app.state.auth_enabled:
        user_id = request.session.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="not authenticated")
        return cast(str, user_id)
    return cast(str, request.app.state.default_user_id)
