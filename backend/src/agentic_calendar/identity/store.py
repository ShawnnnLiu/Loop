"""``GoogleCredentialStore`` protocol + in-memory twin.

One record per app ``user_id``; the Google ``sub`` is a unique secondary key so
login can resolve a returning Google account back to its existing ``user_id``
(:meth:`get_user_id_for_sub`). The sub↔user_id mapping is strictly 1:1 — a
second user_id claiming an already-linked sub is a typed
:class:`GoogleSubConflictError`, never a silent overwrite that would let one
Google account hijack another user's data.

``encrypted_token`` is opaque ciphertext (see
:class:`agentic_calendar.common.secrets.TokenCipher`); the store never decrypts
or logs it. Mutations (e.g. attaching the dedicated calendar id) rebuild the
frozen record through ``model_validate`` and call :meth:`save` again — the same
"re-validate the merged dump, never ``model_copy``" house rule the other stores
follow. ``delete_for_user`` exists for the data-delete control (ADR-0007).
"""

from __future__ import annotations

import threading
from datetime import datetime
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from agentic_calendar.common.errors import AgenticCalendarError


class GoogleCredentialRecord(BaseModel):
    """One user's Google linkage: identity, encrypted token, calendar id."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    user_id: str = Field(min_length=1)
    google_sub: str = Field(min_length=1)
    email: str = Field(min_length=1)
    encrypted_token: str = Field(min_length=1)
    dedicated_calendar_id: str | None = None
    created_at: datetime
    updated_at: datetime


class GoogleCredentialStoreError(AgenticCalendarError):
    """Base for credential-store errors that callers may catch."""


class GoogleSubConflictError(GoogleCredentialStoreError):
    """A Google account is already linked to a different app user.

    Raised on :meth:`GoogleCredentialStore.save` when the record's
    ``google_sub`` already belongs to another ``user_id`` — preserves the 1:1
    account↔user mapping the login flow relies on.
    """

    def __init__(self, *, existing_user_id: str, attempted_user_id: str) -> None:
        self.existing_user_id = existing_user_id
        self.attempted_user_id = attempted_user_id
        super().__init__(
            "this Google account is already linked to a different user"
        )


@runtime_checkable
class GoogleCredentialStore(Protocol):
    """Read/write surface for per-user Google credentials."""

    def save(self, record: GoogleCredentialRecord) -> None: ...

    def get_by_user(self, user_id: str) -> GoogleCredentialRecord | None: ...

    def get_user_id_for_sub(self, google_sub: str) -> str | None: ...

    def delete_for_user(self, user_id: str) -> int: ...


class InMemoryGoogleCredentialStore:
    """Default store. Thread-safe, ephemeral, non-persistent."""

    def __init__(self) -> None:
        self._by_user: dict[str, GoogleCredentialRecord] = {}
        self._lock = threading.RLock()

    def save(self, record: GoogleCredentialRecord) -> None:
        """Upsert by ``user_id``; reject a ``google_sub`` owned by another user."""
        with self._lock:
            for user_id, existing in self._by_user.items():
                if existing.google_sub == record.google_sub and user_id != record.user_id:
                    raise GoogleSubConflictError(
                        existing_user_id=user_id, attempted_user_id=record.user_id
                    )
            self._by_user[record.user_id] = record

    def get_by_user(self, user_id: str) -> GoogleCredentialRecord | None:
        with self._lock:
            return self._by_user.get(user_id)

    def get_user_id_for_sub(self, google_sub: str) -> str | None:
        with self._lock:
            for user_id, record in self._by_user.items():
                if record.google_sub == google_sub:
                    return user_id
            return None

    def delete_for_user(self, user_id: str) -> int:
        """Remove this user's credential; return the count removed (0 or 1)."""
        with self._lock:
            return 1 if self._by_user.pop(user_id, None) is not None else 0
