"""Per-user calendar wiring for the hosted write path (Increment 4).

Only the write endpoint needs a calendar adapter, and in hosted mode it must
be *this* user's: their decrypted token, bound to *their* dedicated secondary
calendar. :func:`build_user_calendar_service` builds that adapter and swaps it
(plus a matching write manager) into a copy of the shared environment via
``dataclasses.replace`` — reusing every persistent store, so no SQLite
connection is reopened and all mappings/approvals stay in the shared tables.

The dedicated calendar is provisioned once, at connect time (see
``routes_auth``), so this path never creates a calendar — it asserts one
exists. The Google SDK is reached only through ``tools.google_oauth_web``
(``build_service_from_token``); the adapter itself never imports the SDK.
"""

from __future__ import annotations

import dataclasses
import json

from agentic_calendar.app.cycle import CycleError, CycleService
from agentic_calendar.app.environment import AppEnvironment
from agentic_calendar.calendar_writer.google_adapter import (
    GoogleApiHttpTransport,
    GoogleCalendarAdapter,
)
from agentic_calendar.calendar_writer.manager import CalendarWriteManager
from agentic_calendar.common.secrets import TokenCipher
from agentic_calendar.tools.google_oauth_web import build_service_from_token


def build_user_calendar_service(
    env: AppEnvironment, *, user_id: str, token_cipher: TokenCipher
) -> tuple[CycleService, str]:
    """A cycle service whose writes target ``user_id``'s dedicated calendar.

    Returns the service and the dedicated calendar id (to pass to ``write``).
    Raises :class:`CycleError` if the user has not connected Google or has no
    provisioned calendar — both impossible after a successful sign-in, but
    enforced rather than assumed.
    """
    store = env.credential_store
    cred = store.get_by_user(user_id)
    if cred is None:
        raise CycleError(f"user {user_id!r} has not connected a Google account")
    if not cred.dedicated_calendar_id:
        raise CycleError(f"user {user_id!r} has no dedicated calendar provisioned")

    token_json = json.loads(token_cipher.decrypt(cred.encrypted_token))
    service = build_service_from_token(token_json)
    adapter = GoogleCalendarAdapter(
        transport=GoogleApiHttpTransport(service),
        dedicated_calendar_id=cred.dedicated_calendar_id,
    )
    write_manager = CalendarWriteManager(
        adapter=adapter,
        mapping_store=env.mapping_store,
        approval_store=env.approval_store,
        lock_manager=env.lock_manager,
        id_generator=env.id_generator,
        clock=env.clock,
    )
    user_env = dataclasses.replace(
        env, calendar_adapter=adapter, write_manager=write_manager
    )
    return CycleService(user_env), cred.dedicated_calendar_id
