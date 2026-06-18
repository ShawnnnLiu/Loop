"""Hosted-mode entrypoint: build the authenticated web app from the environment.

Run with uvicorn's factory mode (single process — SQLite + WAL is a one-process
store; do NOT run multiple workers against one database file)::

    uvicorn agentic_calendar.app.web.server:create_hosted_app --factory \
        --host 0.0.0.0 --port 8000

All configuration comes from environment variables (never the repo):

* ``SHARED_DB_PATH``            — the one SQLite file every store shares.
* ``GOOGLE_OAUTH_CLIENT_SECRET_FILE`` / ``OAUTH_REDIRECT_URI`` /
  ``APP_SESSION_SECRET`` / ``TESTER_ALLOWLIST`` / ``APP_HTTPS_ONLY`` — see
  :meth:`WebAuthConfig.from_env`.
* ``APP_TOKEN_ENCRYPTION_KEY``  — the Fernet key for token-at-rest encryption.
* ``ANTHROPIC_API_KEY``         — required: real testers' plans use the live
  Anthropic nodes (the fixture nodes only handle the sample profile).
* ``TUNING_PATH``               — optional tuning.toml (journaled overrides).

See ``docs/deploy.md`` for the full deploy + Google Cloud Console runbook.
"""

from __future__ import annotations

import os

from fastapi import FastAPI

from agentic_calendar.app.environment import build_environment
from agentic_calendar.common.secrets import TokenCipher
from agentic_calendar.tools.run_cycle import _live_bundle

from .app import create_app
from .config import WebAuthConfig, WebConfigError


def create_hosted_app() -> FastAPI:
    """Wire the hosted multi-user app from environment configuration.

    Raises :class:`WebConfigError` if a required variable is missing, and
    ``CycleError`` (from the live bundle) if ``ANTHROPIC_API_KEY`` is unset.
    """
    db_path = os.environ.get("SHARED_DB_PATH")
    if not db_path:
        raise WebConfigError("SHARED_DB_PATH is not set")

    env = build_environment(
        nodes_factory=_live_bundle,
        db_path=db_path,
        tuning_path=os.environ.get("TUNING_PATH") or None,
    )
    return create_app(
        env=env,
        auth_config=WebAuthConfig.from_env(),
        token_cipher=TokenCipher.from_env(),
    )
