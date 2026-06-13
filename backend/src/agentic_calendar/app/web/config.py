"""Configuration for the hosted (authenticated) web mode.

When a :class:`WebAuthConfig` is supplied, :func:`create_app` runs in hosted
mode: signed-cookie sessions, the ``/auth`` login flow, and a per-request
``user_id`` derived from the session (never the request body). When it is
absent, the app stays in the Increment-1 localhost dev mode (single configured
user, no auth).

Nothing here is a secret in itself — the session signing key and the OAuth
client secret arrive through the environment (:meth:`from_env`) and are never
committed or logged. The token-encryption key is handled separately by
:class:`agentic_calendar.common.secrets.TokenCipher`.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agentic_calendar.common.errors import AgenticCalendarError


class WebConfigError(AgenticCalendarError):
    """A required web-auth configuration value is missing or malformed."""


@dataclass(frozen=True, slots=True)
class WebAuthConfig:
    """Everything the ``/auth`` flow needs, plus the session-cookie policy."""

    client_config: Mapping[str, Any]
    """The Google "Web application" OAuth client JSON (the ``{"web": {...}}`` dict)."""
    redirect_uri: str
    session_secret: str
    audience: str
    """The OAuth client id — the id_token audience verified on callback."""
    tester_allowlist: frozenset[str]
    """Lower-cased emails permitted to sign in (the ≤100-tester gate, in-app)."""
    https_only: bool = True
    """Session cookie ``Secure`` flag. True in production; tests/localhost set False."""

    @classmethod
    def from_env(cls) -> WebAuthConfig:
        """Build from environment variables (the deploy path).

        ``GOOGLE_OAUTH_CLIENT_SECRET_FILE`` (path to the web client JSON),
        ``OAUTH_REDIRECT_URI``, ``APP_SESSION_SECRET``, ``TESTER_ALLOWLIST``
        (comma-separated emails). ``APP_HTTPS_ONLY=0`` disables the Secure flag
        for local runs.
        """
        secret_file = _require_env("GOOGLE_OAUTH_CLIENT_SECRET_FILE")
        client_config = json.loads(Path(secret_file).read_text())
        web = client_config.get("web")
        if not isinstance(web, Mapping) or not web.get("client_id"):
            raise WebConfigError(
                "client secret JSON must be a Web-application client "
                "(a top-level 'web' object with a 'client_id')"
            )
        allowlist = frozenset(
            email.strip().lower()
            for email in _require_env("TESTER_ALLOWLIST").split(",")
            if email.strip()
        )
        if not allowlist:
            raise WebConfigError("TESTER_ALLOWLIST is empty; no one could sign in")
        return cls(
            client_config=client_config,
            redirect_uri=_require_env("OAUTH_REDIRECT_URI"),
            session_secret=_require_env("APP_SESSION_SECRET"),
            audience=str(web["client_id"]),
            tester_allowlist=allowlist,
            https_only=os.environ.get("APP_HTTPS_ONLY", "1") != "0",
        )

    def allows(self, email: str) -> bool:
        return email.strip().lower() in self.tester_allowlist


def _require_env(var: str) -> str:
    value = os.environ.get(var)
    if not value:
        raise WebConfigError(f"{var} is not set")
    return value
