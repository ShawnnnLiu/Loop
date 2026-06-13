"""JSON API mirroring the operator ``run_cycle`` workflow over ``CycleService``.

One endpoint per cycle command. The mapping to HTTP status is deliberate and
preserves the axiom "every failure produces a typed ``reason_code``":

* A *workflow* failure (validation rejected a plan, a write could not verify)
  is a normal result with ``reason_code`` set and HTTP 200 — the typed code
  travels in the body, exactly as the CLI prints it.
* A *command-precondition* failure (``approve`` before ``propose``, unknown
  user) raises :class:`CycleError` and is translated to HTTP 409 by the
  handler in :mod:`agentic_calendar.app.web.app`.

The acting ``user_id`` always comes from :func:`require_user`, never from the
request body — ``onboard`` overwrites any client-supplied ``user_profile.
user_id`` with it. In Increment 1 that id is a single configured value; the
override is written now so the trust boundary is identical once the id becomes
session-derived (Increment 3).
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from agentic_calendar.app.cycle import DEFAULT_TARGET_CALENDAR_ID, CycleService
from agentic_calendar.contracts.checkin_event import RecoveryAction

from .calendar_service import build_user_calendar_service
from .deps import get_cycle_service, require_user

router = APIRouter(prefix="/api", tags=["cycle"])

# FastAPI's Annotated dependency style keeps these out of argument defaults
# (lint-clean: no function calls in defaults).
Service = Annotated[CycleService, Depends(get_cycle_service)]
ActingUser = Annotated[str, Depends(require_user)]


class ProposeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    free_busy: list[dict[str, Any]] = []
    horizon_days: int | None = None
    recovery_mode: RecoveryAction | None = None


class ApproveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str | None = None
    reject: bool = False


class WriteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str | None = None
    target_calendar_id: str = DEFAULT_TARGET_CALENDAR_ID
    dry_run: bool = False


def _json(result: BaseModel) -> JSONResponse:
    """Serialize exactly as the CLI does (``model_dump_json``) — no FastAPI
    response-model coercion, so the body is byte-identical to the operator
    surface."""
    return JSONResponse(content=result.model_dump(mode="json"))


@router.post("/onboard")
def onboard(
    service: Service,
    user_id: ActingUser,
    payload: Annotated[dict[str, Any], Body()],
) -> JSONResponse:
    profile = payload.get("user_profile")
    if isinstance(profile, dict):
        # Trust boundary: the acting user owns the record, not whatever id the
        # client put in the body (identical override to Increment 3's session id).
        payload = {**payload, "user_profile": {**profile, "user_id": user_id}}
    return _json(service.onboard(payload))


@router.post("/propose")
def propose(
    service: Service,
    user_id: ActingUser,
    body: ProposeRequest | None = None,
) -> JSONResponse:
    body = body or ProposeRequest()
    return _json(
        service.propose(
            user_id,
            free_busy=body.free_busy,
            horizon_days=body.horizon_days,
            recovery_mode=body.recovery_mode,
        )
    )


@router.post("/approve")
def approve(
    service: Service,
    user_id: ActingUser,
    body: ApproveRequest | None = None,
) -> JSONResponse:
    body = body or ApproveRequest()
    return _json(service.approve(user_id, run_id=body.run_id, reject=body.reject))


@router.post("/write")
def write(
    request: Request,
    service: Service,
    user_id: ActingUser,
    body: WriteRequest | None = None,
) -> JSONResponse:
    body = body or WriteRequest()
    if request.app.state.auth_enabled:
        # Hosted mode: write to THIS user's dedicated calendar via a per-user
        # adapter. The target id comes from their stored credential, never the
        # request body — a client cannot redirect the write to another calendar.
        user_service, calendar_id = build_user_calendar_service(
            request.app.state.env,
            user_id=user_id,
            token_cipher=request.app.state.token_cipher,
        )
        return _json(
            user_service.write(
                user_id,
                run_id=body.run_id,
                target_calendar_id=calendar_id,
                dry_run=body.dry_run,
            )
        )
    # Dev mode: shared in-memory adapter, target from the request.
    return _json(
        service.write(
            user_id,
            run_id=body.run_id,
            target_calendar_id=body.target_calendar_id,
            dry_run=body.dry_run,
        )
    )


@router.post("/ingest")
def ingest(
    service: Service,
    user_id: ActingUser,
    payload: Annotated[list[dict[str, Any]] | dict[str, Any], Body()],
) -> JSONResponse:
    payloads = payload if isinstance(payload, list) else [payload]
    return _json(service.ingest(user_id, payloads))


@router.get("/status")
def status(service: Service, user_id: ActingUser) -> JSONResponse:
    return _json(service.status(user_id))
