"""Server-rendered HTML pages (F0b) — the basic hosted UI.

The core journey: connect Google (login), see your plan (home), review the
draft schedule with its canonical payload hash, approve, and write to your
calendar. Minimal CSS, no JS framework. Registered only in hosted mode, since
every page needs the session for both auth and CSRF.

State-changing POSTs carry a per-session CSRF token (a hidden form field
validated against the session). Combined with the SameSite=lax session cookie,
that closes the gap the JSON API left open. Onboarding is still done via the
JSON API for now — a profile form is a follow-up.
"""

from __future__ import annotations

import secrets
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from agentic_calendar.app.cycle import HASH_CANONICALIZATION_VERSION
from agentic_calendar.contracts.hashing import canonical_payload_hash

from .calendar_service import build_user_calendar_service
from .deps import get_cycle_service

router = APIRouter(tags=["pages"])
_templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

_USER_KEY = "user_id"
_CSRF_KEY = "csrf_token"

CsrfField = Annotated[str, Form()]


def _user(request: Request) -> str | None:
    return request.session.get(_USER_KEY)


def _require_user(request: Request) -> str:
    user_id = request.session.get(_USER_KEY)
    if not user_id:
        raise HTTPException(status_code=401, detail="not authenticated")
    return str(user_id)


def _csrf(request: Request) -> str:
    """Get-or-create this session's CSRF token (rendered into every form)."""
    token = request.session.get(_CSRF_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        request.session[_CSRF_KEY] = token
    return str(token)


def _check_csrf(request: Request, token: str) -> None:
    expected = request.session.get(_CSRF_KEY)
    if not expected or token != expected:
        raise HTTPException(status_code=403, detail="invalid CSRF token")


def _page(request: Request, name: str, **context: object) -> Response:
    return _templates.TemplateResponse(
        request=request,
        name=name,
        context={"email": request.session.get("email"), "csrf_token": _csrf(request), **context},
    )


@router.get("/", response_class=HTMLResponse)
def index(request: Request) -> Response:
    if _user(request):
        return RedirectResponse("/home", status_code=303)
    return _page(request, "login.html")


@router.get("/home", response_class=HTMLResponse)
def home(request: Request) -> Response:
    if not _user(request):
        return RedirectResponse("/", status_code=303)
    status = get_cycle_service(request).status(_require_user(request))
    return _page(request, "home.html", status=status)


@router.get("/draft", response_class=HTMLResponse)
def draft_page(request: Request) -> Response:
    if not _user(request):
        return RedirectResponse("/", status_code=303)
    user_id = _require_user(request)
    status = get_cycle_service(request).status(user_id)
    draft = None
    payload_hash = None
    if status.draft_schedule_id:
        draft = request.app.state.env.state.get_draft(status.draft_schedule_id)
        if draft is not None:
            payload_hash = canonical_payload_hash(draft, HASH_CANONICALIZATION_VERSION)
    return _page(request, "draft.html", status=status, draft=draft, payload_hash=payload_hash)


@router.post("/ui/propose")
def ui_propose(request: Request, csrf_token: CsrfField) -> RedirectResponse:
    _check_csrf(request, csrf_token)
    get_cycle_service(request).propose(_require_user(request))
    return RedirectResponse("/draft", status_code=303)


@router.post("/ui/approve")
def ui_approve(
    request: Request,
    csrf_token: CsrfField,
    action: Annotated[str, Form()] = "approve",
) -> RedirectResponse:
    _check_csrf(request, csrf_token)
    get_cycle_service(request).approve(_require_user(request), reject=action == "reject")
    return RedirectResponse("/draft", status_code=303)


@router.post("/ui/write")
def ui_write(request: Request, csrf_token: CsrfField) -> RedirectResponse:
    _check_csrf(request, csrf_token)
    user_id = _require_user(request)
    user_service, calendar_id = build_user_calendar_service(
        request.app.state.env, user_id=user_id, token_cipher=request.app.state.token_cipher
    )
    user_service.write(user_id, target_calendar_id=calendar_id)
    return RedirectResponse("/home", status_code=303)


@router.post("/ui/logout")
def ui_logout(request: Request, csrf_token: CsrfField) -> RedirectResponse:
    _check_csrf(request, csrf_token)
    request.session.clear()
    return RedirectResponse("/", status_code=303)
