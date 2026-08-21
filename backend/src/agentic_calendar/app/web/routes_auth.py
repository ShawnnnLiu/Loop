"""Sign-in / sign-out routes — the authentication trust boundary.

The flow: ``/auth/login`` mints a random CSRF ``state``, stashes it in the
session, and redirects to Google's consent screen; Google redirects back to
``/auth/callback`` with a ``code`` and the echoed ``state``. The callback
verifies the state, exchanges the code, verifies the signed-in identity,
resolves the Google ``sub`` to a stable app ``user_id``, encrypts and persists
the token, and writes ``user_id`` into the session. From then on every request's acting user comes from that signed
cookie (see :func:`agentic_calendar.app.web.deps.require_user`) — never from a
form field, query param, or path.

The Google SDK is reached only through ``tools.google_oauth_web`` (which holds
the imports); this module passes plain dicts and reads back a small identity.
"""

from __future__ import annotations

import hashlib
import json
import secrets

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse

from agentic_calendar.app.environment import AppEnvironment
from agentic_calendar.app.web.config import WebAuthConfig
from agentic_calendar.common.secrets import TokenCipher
from agentic_calendar.identity.store import GoogleCredentialRecord
from agentic_calendar.tools.google_oauth_web import (
    build_authorization_url,
    build_service_from_token,
    create_dedicated_calendar,
    dedicated_calendar_exists,
    exchange_code,
    identity_from_token,
)

router = APIRouter(prefix="/auth", tags=["auth"])

# Pending login attempts, stored in the session as {state: code_verifier}.
# A dict (not a single slot) because login attempts overlap in practice: while
# one tab sits on Google's consent screen, another tab hitting /auth/login
# (e.g. the SPA's 401 redirect) must not invalidate the first tab's state —
# a single slot made that a self-perpetuating "invalid or missing oauth state"
# loop. Capped so the signed cookie stays small; oldest attempts evict first
# (JSON round-trips preserve dict insertion order).
_OAUTH_PENDING_KEY = "oauth_pending"
_MAX_PENDING_LOGINS = 5


def _config(request: Request) -> WebAuthConfig:
    config: WebAuthConfig = request.app.state.auth_config
    return config


def _user_id_for_sub(sub: str) -> str:
    """A stable, opaque app user id derived from the Google subject id."""
    return "u_" + hashlib.sha256(sub.encode("utf-8")).hexdigest()[:24]


@router.get("/login")
def login(request: Request) -> RedirectResponse:
    config = _config(request)
    state = secrets.token_urlsafe(32)
    url, code_verifier = build_authorization_url(
        client_config=config.client_config,
        redirect_uri=config.redirect_uri,
        state=state,
    )
    # PKCE spans both requests: stash the verifier (keyed by the CSRF state) so
    # the callback can replay it.
    pending = dict(request.session.get(_OAUTH_PENDING_KEY) or {})
    pending[state] = code_verifier
    while len(pending) > _MAX_PENDING_LOGINS:
        del pending[next(iter(pending))]
    request.session[_OAUTH_PENDING_KEY] = pending
    return RedirectResponse(url, status_code=307)


@router.get("/callback")
def callback(request: Request, code: str, state: str) -> RedirectResponse:
    config = _config(request)
    pending = dict(request.session.get(_OAUTH_PENDING_KEY) or {})
    code_verifier = pending.pop(state, None)
    if code_verifier is None:
        # Defeats login-CSRF: the state must match one this session minted.
        # Each state is single-use, so replaying a callback URL lands here too.
        raise HTTPException(status_code=400, detail="invalid or missing oauth state")
    if pending:
        request.session[_OAUTH_PENDING_KEY] = pending
    else:
        request.session.pop(_OAUTH_PENDING_KEY, None)

    token_json = exchange_code(
        client_config=config.client_config,
        redirect_uri=config.redirect_uri,
        code=code,
        state=state,
        code_verifier=code_verifier,
    )
    identity = identity_from_token(token_json, audience=config.audience)

    env: AppEnvironment = request.app.state.env
    cipher: TokenCipher = request.app.state.token_cipher
    store = env.credential_store

    existing_user_id = store.get_user_id_for_sub(identity.sub)
    if existing_user_id is not None:
        user_id = existing_user_id
        existing = store.get_by_user(user_id)
    else:
        user_id = _user_id_for_sub(identity.sub)
        existing = None

    # Provision the dedicated secondary calendar on first connect, and reuse it
    # on later sign-ins — but RE-provision if the stored calendar is gone
    # (deleted in Google, lost across environments). Without this reachability
    # check a stale id is trusted forever and every write 404s with no user-side
    # recovery. Each user writes only to their own calendar, so the adapter's
    # "never touch primary / another calendar" guard holds.
    dedicated_calendar_id = existing.dedicated_calendar_id if existing else None
    service = build_service_from_token(token_json)
    if dedicated_calendar_id is None or not dedicated_calendar_exists(
        service, dedicated_calendar_id
    ):
        dedicated_calendar_id = create_dedicated_calendar(
            service, summary=f"Agentic Calendar ({user_id})"
        )

    now = env.clock.now()
    record = GoogleCredentialRecord.model_validate(
        {
            "user_id": user_id,
            "google_sub": identity.sub,
            "email": identity.email,
            "encrypted_token": cipher.encrypt(json.dumps(dict(token_json))),
            "dedicated_calendar_id": dedicated_calendar_id,
            "created_at": existing.created_at if existing else now,
            "updated_at": now,
        }
    )
    store.save(record)

    request.session["user_id"] = user_id
    request.session["email"] = identity.email
    # Land in the app, not the marketing root: "/app" is the SPA entry that
    # forwards to onboarding or today based on the user's state.
    return RedirectResponse("/app", status_code=307)


@router.post("/logout")
def logout(request: Request) -> JSONResponse:
    request.session.clear()
    return JSONResponse(content={"status": "logged out"})
