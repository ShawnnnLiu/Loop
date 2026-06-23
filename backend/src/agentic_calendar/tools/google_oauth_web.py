"""Web (redirect) OAuth handshake for the hosted multi-user frontend.

The operator CLI's :mod:`agentic_calendar.tools.google_calendar_auth` runs the
*installed-app* desktop flow (one shared token on disk). A hosted app instead
needs the *web server* authorization-code flow: the user clicks "Connect", is
redirected to Google, and Google redirects back to a callback with a code the
server exchanges for that user's tokens.

This module is, like its sibling, a home for ``google.*`` /
``google_auth_oauthlib`` imports (the boundary grep allows them only under
``tools/`` and ``llm_nodes/``); imports stay function-local so nothing here
loads the SDK until a handshake actually runs. The web layer in ``app/web``
calls these functions and passes/receives only plain token-JSON dicts and the
opaque Calendar ``service`` object — it never imports the SDK itself.

Scopes combine sign-in (``openid``/``email``/``profile``) with calendar write
(``calendar.events``): one consent both authenticates the user and authorizes
the dedicated-calendar writes. ``calendar.events`` is a *sensitive* scope, so a
closed group of ≤100 testers needs no Google app verification.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from agentic_calendar.common.errors import AgenticCalendarError

WEB_SCOPES = (
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    # calendar.app.created: create a secondary calendar AND manage its events.
    # (calendar.events alone cannot create a calendar — calendars.insert 403s.)
    "https://www.googleapis.com/auth/calendar.app.created",
    # calendar.freebusy: read the user's real busy ranges (busy/free only, never
    # event content) so the scheduler avoids existing commitments. Sensitive
    # scope — already-connected users must reconnect once to grant it; until
    # then freebusy.query 403s and the caller falls back to no calendar data.
    "https://www.googleapis.com/auth/calendar.freebusy",
)


class GoogleOAuthError(AgenticCalendarError):
    """A web OAuth handshake step failed (bad token, missing id_token, …)."""


@dataclass(frozen=True, slots=True)
class GoogleIdentity:
    """The verified identity from a sign-in: stable ``sub`` plus ``email``."""

    sub: str
    email: str


def build_authorization_url(
    *, client_config: Mapping[str, Any], redirect_uri: str, state: str
) -> tuple[str, str]:
    """The Google consent URL plus the PKCE ``code_verifier`` to redirect to.

    ``access_type=offline`` + ``prompt=consent`` ensures a refresh token comes
    back so the server can write to the calendar later without the user present.
    ``state`` is the caller's CSRF token, echoed back on the callback.

    The library uses PKCE: it generates a one-time ``code_verifier`` here and
    sends its hash to Google. The verifier is needed again at the token
    exchange (a *separate* request), so the caller MUST persist it (in the
    session) and hand it to :func:`exchange_code` — otherwise Google rejects
    the exchange with "Missing code verifier".
    """
    from google_auth_oauthlib.flow import Flow

    flow = Flow.from_client_config(
        client_config, scopes=list(WEB_SCOPES), redirect_uri=redirect_uri
    )
    url, _state = flow.authorization_url(
        access_type="offline", include_granted_scopes="true", prompt="consent", state=state
    )
    return str(url), str(flow.code_verifier or "")


def exchange_code(
    *,
    client_config: Mapping[str, Any],
    redirect_uri: str,
    code: str,
    state: str,
    code_verifier: str | None = None,
) -> dict[str, Any]:
    """Exchange the callback ``code`` for this user's token JSON.

    ``code_verifier`` is the PKCE verifier minted in :func:`build_authorization_url`
    and carried through the session — it must be replayed here.

    Returns the authorized-user token dict (token, refresh_token, client id/
    secret, scopes) with ``id_token`` guaranteed present so the caller can
    verify the signed-in identity. The web layer encrypts this before storing.
    """
    from google_auth_oauthlib.flow import Flow

    flow = Flow.from_client_config(
        client_config, scopes=list(WEB_SCOPES), redirect_uri=redirect_uri, state=state
    )
    if code_verifier:
        flow.code_verifier = code_verifier
    # Google returns the union of previously-granted scopes (incremental auth,
    # via include_granted_scopes) and usually reorders them, so the granted set
    # won't equal the requested set. Tell oauthlib not to reject that — we only
    # ever rely on calendar.app.created; any extra grant is harmless.
    os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")
    try:
        flow.fetch_token(code=code)
    except Exception as exc:
        # oauthlib / transport failures (invalid_grant, scope changes, network)
        # become a typed error so the surface returns a clean 400, not a 500.
        raise GoogleOAuthError(f"OAuth token exchange failed: {exc}") from exc
    creds = flow.credentials
    token_json: dict[str, Any] = json.loads(creds.to_json())
    if "id_token" not in token_json and getattr(creds, "id_token", None):
        token_json["id_token"] = creds.id_token
    return token_json


def identity_from_token(token_json: Mapping[str, Any], *, audience: str) -> GoogleIdentity:
    """Verify the ``id_token`` and return the signed-in identity.

    ``audience`` is the OAuth client id. Verification fetches Google's signing
    certificates; a back-channel token (obtained server-to-server over TLS) is
    already trusted, but verifying the signature and audience is cheap defense.
    """
    from google.auth.transport import requests as google_requests
    from google.oauth2 import id_token as google_id_token

    raw = token_json.get("id_token")
    if not raw:
        raise GoogleOAuthError(
            "token response carried no id_token; request the openid scope"
        )
    claims = google_id_token.verify_oauth2_token(  # type: ignore[no-untyped-call]
        raw, google_requests.Request(), audience
    )
    sub = claims.get("sub")
    email = claims.get("email")
    if not sub or not email:
        raise GoogleOAuthError("id_token is missing the sub or email claim")
    return GoogleIdentity(sub=str(sub), email=str(email))


def build_service_from_token(token_json: Mapping[str, Any]) -> Any:
    """Build an authorized Calendar v3 ``service`` from a stored token dict.

    The web analogue of ``google_calendar_auth.build_calendar_service`` (which
    reads a file): tokens here come decrypted from the per-user credential
    store, not from disk.
    """
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    creds = Credentials.from_authorized_user_info(  # type: ignore[no-untyped-call]
        dict(token_json), list(WEB_SCOPES)
    )
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def create_dedicated_calendar(
    service: Any, *, summary: str, time_zone: str = "UTC"
) -> str:
    """Create a new secondary calendar and return its id.

    Each user gets their own dedicated calendar so the adapter's "never write
    to primary" guard holds and one user's events never land on another's.
    """
    try:
        created = service.calendars().insert(
            body={"summary": summary, "timeZone": time_zone}
        ).execute()
    except Exception as exc:
        # e.g. an insufficient-scope 403 from the Calendar API — typed, not a 500.
        raise GoogleOAuthError(f"could not create the dedicated calendar: {exc}") from exc
    return str(created["id"])


def dedicated_calendar_exists(service: Any, calendar_id: str) -> bool:
    """Whether ``calendar_id`` is still reachable for this token.

    Returns ``False`` only when the calendar is definitively gone (HTTP 404/410)
    — the signal to re-provision a fresh one on reconnect, so a deleted calendar
    does not 404 the write path forever. Any other outcome (success, or an
    ambiguous error such as a transient 5xx or an insufficient-scope 403 that
    re-provisioning would not fix) returns ``True``, so a blip never spawns a
    duplicate calendar.
    """
    try:
        service.calendars().get(calendarId=calendar_id).execute()
    except Exception as exc:
        try:
            from googleapiclient.errors import HttpError
        except ImportError:  # pragma: no cover - dependency present in dev/prod
            return True
        # Missing (404/410) → re-provision; any other error is ambiguous, so
        # treat the calendar as still present and never spawn a duplicate.
        return not (isinstance(exc, HttpError) and int(exc.resp.status) in (404, 410))
    return True
