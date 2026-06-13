"""Sign-in / sign-out routes — the authentication trust boundary.

The flow: ``/auth/login`` mints a random CSRF ``state``, stashes it in the
session, and redirects to Google's consent screen; Google redirects back to
``/auth/callback`` with a ``code`` and the echoed ``state``. The callback
verifies the state, exchanges the code, verifies the signed-in identity,
enforces the tester allowlist, resolves the Google ``sub`` to a stable app
``user_id``, encrypts and persists the token, and writes ``user_id`` into the
session. From then on every request's acting user comes from that signed
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
    exchange_code,
    identity_from_token,
)

router = APIRouter(prefix="/auth", tags=["auth"])

_OAUTH_STATE_KEY = "oauth_state"


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
    request.session[_OAUTH_STATE_KEY] = state
    url = build_authorization_url(
        client_config=config.client_config,
        redirect_uri=config.redirect_uri,
        state=state,
    )
    return RedirectResponse(url, status_code=307)


@router.get("/callback")
def callback(request: Request, code: str, state: str) -> RedirectResponse:
    config = _config(request)
    expected = request.session.pop(_OAUTH_STATE_KEY, None)
    if not expected or state != expected:
        # Defeats login-CSRF: the state must match the one this session minted.
        raise HTTPException(status_code=400, detail="invalid or missing oauth state")

    token_json = exchange_code(
        client_config=config.client_config,
        redirect_uri=config.redirect_uri,
        code=code,
        state=state,
    )
    identity = identity_from_token(token_json, audience=config.audience)
    if not config.allows(identity.email):
        # The ≤100-tester gate, enforced in-app regardless of Google console config.
        raise HTTPException(status_code=403, detail="not on the tester allowlist")

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

    now = env.clock.now()
    record = GoogleCredentialRecord.model_validate(
        {
            "user_id": user_id,
            "google_sub": identity.sub,
            "email": identity.email,
            "encrypted_token": cipher.encrypt(json.dumps(dict(token_json))),
            # Preserve a previously-created dedicated calendar across re-logins.
            "dedicated_calendar_id": existing.dedicated_calendar_id if existing else None,
            "created_at": existing.created_at if existing else now,
            "updated_at": now,
        }
    )
    store.save(record)

    request.session["user_id"] = user_id
    request.session["email"] = identity.email
    return RedirectResponse("/", status_code=307)


@router.post("/logout")
def logout(request: Request) -> JSONResponse:
    request.session.clear()
    return JSONResponse(content={"status": "logged out"})
