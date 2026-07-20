"""OAuth bootstrap for the Google Calendar adapter (Phase 9c). Module-only.

    uv run python -m agentic_calendar.tools.google_calendar_auth \
        --credentials path/to/client_secret.json

Runs the installed-app OAuth flow in a local browser ONCE and writes the
resulting token to ``--token-out`` (default ``.secrets/google_token.json``).
The operator runs this themselves; the assistant never does. Credentials and
tokens are secrets: the default location is gitignored, the file is written
``0600``, and nothing from either file is ever printed or logged.

This module is the ONLY home for ``google.*`` / ``google_auth_oauthlib``
imports (the boundary grep allows them solely under ``tools/`` and
``llm_nodes/``); ``calendar_writer`` receives a pre-built ``service`` object
through :func:`build_calendar_service` and never touches the SDK itself.

Scope: ``calendar.events`` only — enough to insert/read/delete/list events on
the dedicated secondary calendar, and nothing else (no calendar management,
no other Google data).

The Desktop client for this flow must live in a SEPARATE Google Cloud project
from the hosted web app: Google's Verification Center flags every scope a
project's clients actually request, so running this CLI against the production
project re-adds ``calendar.events`` to its verification surface. The
production project's Desktop client was deleted on 2026-07-19 for this reason;
create a personal dev project if the CLI is ever needed again.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

SCOPES = ("https://www.googleapis.com/auth/calendar.events",)

DEFAULT_TOKEN_PATH = Path(".secrets/google_token.json")


def build_calendar_service(*, token_path: Path = DEFAULT_TOKEN_PATH) -> Any:
    """Build an authorized Calendar v3 ``service`` from a stored token.

    Refreshes an expired token in place when a refresh token is present.
    Raises ``FileNotFoundError`` with a pointer to this CLI when the operator
    has not run the auth flow yet.
    """
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    if not token_path.exists():
        raise FileNotFoundError(
            f"no Google token at {token_path}; run "
            "`uv run python -m agentic_calendar.tools.google_calendar_auth "
            "--credentials <client_secret.json>` first"
        )
    creds = Credentials.from_authorized_user_file(  # type: ignore[no-untyped-call]
        str(token_path), list(SCOPES)
    )
    if not creds.valid and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        _write_token(token_path, creds.to_json())
    if not creds.valid:
        raise RuntimeError(
            f"Google token at {token_path} is invalid and could not be "
            "refreshed; re-run the auth flow"
        )
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def _write_token(token_path: Path, token_json: str) -> None:
    """Write the token file readable by the owner only; never echo contents."""
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(token_json)
    token_path.chmod(0o600)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="google_calendar_auth",
        description="Run the one-time Google OAuth flow and store the token.",
    )
    parser.add_argument(
        "--credentials",
        type=Path,
        required=True,
        help="OAuth client secret JSON downloaded from Google Cloud Console",
    )
    parser.add_argument(
        "--token-out",
        type=Path,
        default=DEFAULT_TOKEN_PATH,
        help=f"where to store the authorized token (default: {DEFAULT_TOKEN_PATH})",
    )
    args = parser.parse_args(argv)

    from google_auth_oauthlib.flow import InstalledAppFlow

    if not args.credentials.exists():
        print(f"error: credentials file not found: {args.credentials}", file=sys.stderr)
        return 1
    flow = InstalledAppFlow.from_client_secrets_file(
        str(args.credentials), list(SCOPES)
    )
    creds = flow.run_local_server(port=0)
    _write_token(args.token_out, creds.to_json())
    print(
        f"token written to {args.token_out} (scope: calendar.events). "
        "Keep it out of version control."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
