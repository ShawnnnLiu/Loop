"""FastAPI request dependencies: resolve the cycle service and the acting user.

These two seams are the whole point of keeping a ``deps`` module: in
Increment 1 the service is a single process-wide instance and the user is a
single configured id, but Increments 3-4 replace :func:`require_user` with a
session lookup (the trust boundary — the acting ``user_id`` is *never* taken
from the request body) and :func:`get_cycle_service` with a per-user build
over that user's stored Google credentials. Routes depend on these names, so
that later swap touches only this file.
"""

from __future__ import annotations

from typing import cast

from fastapi import Request

from agentic_calendar.app.cycle import CycleService


def get_cycle_service(request: Request) -> CycleService:
    """The cycle service wired at app startup (see ``app.state.cycle_service``)."""
    return cast(CycleService, request.app.state.cycle_service)


def require_user(request: Request) -> str:
    """The acting user id.

    Increment 1: the single configured id stored on ``app.state``. This is the
    seam that becomes session-derived in Increment 3 — by then it raises 401
    when no authenticated session is present, and the id is read from the
    signed cookie, never from a form field, query param, or path.
    """
    return cast(str, request.app.state.default_user_id)
