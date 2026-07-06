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
* ``SPA_DIST_DIR`` / ``LANDING_INDEX`` / ``HOW_ITS_BUILT_INDEX`` — optional
  overrides for the built SPA, the static landing, and the static
  engineering-story page (defaults are the in-repo copies).
* ``CANONICAL_HOST``            — optional bare hostname; requests under any
  other host (e.g. the old ``<app>.fly.dev`` name after a custom-domain
  cutover) are 301-redirected to it. Unset means no redirect.

See ``docs/deploy.md`` for the full deploy + Google Cloud Console runbook.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI

from agentic_calendar.app.environment import build_environment
from agentic_calendar.common.secrets import TokenCipher
from agentic_calendar.tools.run_cycle import _live_bundle

from .app import create_app, default_how_its_built, default_landing_index, default_spa_dist
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
    # The built SPA + static landing: env vars override the in-repo defaults
    # (frontend/dist and landing/index.html).
    spa_override = os.environ.get("SPA_DIST_DIR")
    spa_dist = Path(spa_override) if spa_override else default_spa_dist()
    landing_override = os.environ.get("LANDING_INDEX")
    landing_index = Path(landing_override) if landing_override else default_landing_index()
    built_override = os.environ.get("HOW_ITS_BUILT_INDEX")
    how_its_built = Path(built_override) if built_override else default_how_its_built()
    return create_app(
        env=env,
        auth_config=WebAuthConfig.from_env(),
        token_cipher=TokenCipher.from_env(),
        spa_dist=spa_dist,
        landing_index=landing_index,
        how_its_built=how_its_built,
        canonical_host=os.environ.get("CANONICAL_HOST") or None,
    )
