"""Durable prose attachments (UX pass B5).

Spec: ``docs/specs/prose-attachment.schema.md``. Persists the prose the
product already generated for the user — drift reflections and validation
explanations — so read surfaces can say *what it already said* instead of a
bare reason code. Display and advisory-context data only: no routing,
validation, scheduling, approval, or write decision may read these records
(LLM prose never controls workflow state). Same placement rationale as
``call_log.py``: an LLM-artifact record living in the only LLM zone.
"""

from __future__ import annotations

import threading
from datetime import datetime
from enum import StrEnum
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, model_validator

from agentic_calendar.common.errors import AgenticCalendarError
from agentic_calendar.contracts.reason_codes import ReasonCode


class ProseAttachmentStoreError(AgenticCalendarError):
    """Base for prose-attachment store errors."""


class ProseAttachmentAlreadyExistsError(ProseAttachmentStoreError):
    """Attempted to append a ``prose_attachment_id`` that already exists."""


class ProseAttachmentKind(StrEnum):
    """Which prose node produced the attachment."""

    REFLECTION = "reflection"
    EXPLANATION = "explanation"


class ProseAttachmentRecord(BaseModel):
    """One persisted user-facing prose output (append-only).

    ``reason_code`` is a display *copy* of the run's typed cause — the run
    record stays authoritative; this record can never smuggle prose into
    routing decisions.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    prose_attachment_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    plan_version: str | None = None
    kind: ProseAttachmentKind
    summary: str = Field(min_length=1)
    detail: tuple[str, ...] = ()
    reason_code: ReasonCode | None = None
    created_at: datetime

    @model_validator(mode="after")
    def _created_at_aware(self) -> ProseAttachmentRecord:
        if self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        return self


@runtime_checkable
class ProseAttachmentStore(Protocol):
    """Append/read surface for prose attachments."""

    def append(self, record: ProseAttachmentRecord) -> None: ...

    def list_for_run(self, run_id: str) -> list[ProseAttachmentRecord]: ...

    def list_for_user(self, user_id: str) -> list[ProseAttachmentRecord]: ...

    def latest_for_run(
        self, run_id: str, *, kind: ProseAttachmentKind
    ) -> ProseAttachmentRecord | None: ...

    def delete_for_user(self, user_id: str) -> int: ...


class InMemoryProseAttachmentStore:
    """Default store. Thread-safe, ephemeral, append-only (insertion order)."""

    def __init__(self) -> None:
        self._by_id: dict[str, ProseAttachmentRecord] = {}
        self._order: list[str] = []
        self._lock = threading.RLock()

    def append(self, record: ProseAttachmentRecord) -> None:
        with self._lock:
            if record.prose_attachment_id in self._by_id:
                raise ProseAttachmentAlreadyExistsError(record.prose_attachment_id)
            self._by_id[record.prose_attachment_id] = record
            self._order.append(record.prose_attachment_id)

    def list_for_run(self, run_id: str) -> list[ProseAttachmentRecord]:
        with self._lock:
            return [
                self._by_id[i] for i in self._order if self._by_id[i].run_id == run_id
            ]

    def list_for_user(self, user_id: str) -> list[ProseAttachmentRecord]:
        with self._lock:
            return [
                self._by_id[i] for i in self._order if self._by_id[i].user_id == user_id
            ]

    def latest_for_run(
        self, run_id: str, *, kind: ProseAttachmentKind
    ) -> ProseAttachmentRecord | None:
        with self._lock:
            for attachment_id in reversed(self._order):
                record = self._by_id[attachment_id]
                if record.run_id == run_id and record.kind is kind:
                    return record
            return None

    def delete_for_user(self, user_id: str) -> int:
        """Erase a user's derived prose (they are personal data — spec rule)."""
        with self._lock:
            doomed = [i for i in self._order if self._by_id[i].user_id == user_id]
            for attachment_id in doomed:
                del self._by_id[attachment_id]
            self._order = [i for i in self._order if i not in set(doomed)]
            return len(doomed)
