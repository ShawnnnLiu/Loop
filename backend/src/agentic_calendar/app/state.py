"""App-plane state: onboarding, syllabus, drafts, and persisted run records.

The regions own their domain stores (plan versions, approvals, telemetry, …).
What no region owns is the *application* state a multi-invocation operator
flow needs: which user is onboarded (and in which timezone), the validated
syllabus a replan re-enters the planner with, the draft schedules awaiting
approval, and where each supervisor run currently stands. That state lives
here, keyed and persisted exactly like the region stores (Phase 9a kernel),
so an ``approve`` tomorrow can hash-recheck the same draft ``propose``
produced today.

``RunRecord`` persists the supervisor's *current state* only — never prompts,
prose, or calendar text. Control-plane state stays explicit and typed
(axiom 01: no hidden control plane).
"""

from __future__ import annotations

import threading
from datetime import datetime
from enum import StrEnum
from typing import Protocol, runtime_checkable
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, model_validator

from agentic_calendar.common.errors import AgenticCalendarError
from agentic_calendar.common.sqlite import SqliteDatabase
from agentic_calendar.contracts.checkin_event import RecoveryAction
from agentic_calendar.contracts.draft_schedule import DraftSchedule
from agentic_calendar.contracts.motivation_profile import MotivationProfile
from agentic_calendar.contracts.reason_codes import ReasonCode
from agentic_calendar.contracts.syllabus_units import SyllabusUnits
from agentic_calendar.contracts.user_profile import UserProfile
from agentic_calendar.supervisor.state import SupervisorState


class AppStateError(AgenticCalendarError):
    """Base for app-state-store errors that callers may catch."""


class DraftAlreadyExistsError(AppStateError):
    """Attempted to save a ``draft_schedule_id`` that already exists.

    Drafts are immutable once produced: the approval hash is computed over
    the stored draft, so replacing it in place would silently invalidate a
    pending approval (axiom 06 hash-recheck).
    """


class OnboardingRecord(BaseModel):
    """One user's onboarding bundle.

    ``timezone`` lives here (not on ``UserProfile``) because it is app-plane
    context: check-in cadence and quiet hours are evaluated in the user's
    local time, but no contract carries a timezone today.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    user_id: str = Field(min_length=1)
    user_profile: UserProfile
    timezone: str = Field(min_length=1)
    motivation_profile: MotivationProfile | None = None
    # Opt-in to inbound calendar reconciliation (adopting the user's direct
    # calendar edits). Off by default: the in-app schedule is the system of
    # record, so treating the external calendar as authoritative is opt-in
    # (axiom 06 lines 249-253; calendar-reconciliation spec). Defaulted so
    # existing persisted onboarding rows deserialize unchanged.
    inbound_calendar_sync_enabled: bool = False
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def _timestamps_aware(self) -> OnboardingRecord:
        if self.created_at.tzinfo is None or self.updated_at.tzinfo is None:
            raise ValueError("onboarding timestamps must be timezone-aware")
        if self.updated_at < self.created_at:
            raise ValueError("updated_at must not precede created_at")
        return self

    @model_validator(mode="after")
    def _ids_consistent(self) -> OnboardingRecord:
        if self.user_profile.user_id != self.user_id:
            raise ValueError("user_profile.user_id must match onboarding user_id")
        if (
            self.motivation_profile is not None
            and self.motivation_profile.user_id != self.user_id
        ):
            raise ValueError("motivation_profile.user_id must match onboarding user_id")
        return self

    @model_validator(mode="after")
    def _timezone_resolves(self) -> OnboardingRecord:
        try:
            ZoneInfo(self.timezone)
        except (KeyError, ValueError) as exc:
            raise ValueError(f"unknown IANA timezone {self.timezone!r}") from exc
        return self

    def tzinfo(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)


class ReplanKind(StrEnum):
    """Why a replan was required — decides which deterministic path runs it."""

    RECOVERY = "recovery"
    RECALIBRATION = "recalibration"


class RunRecord(BaseModel):
    """Where one supervisor run currently stands, persisted per transition.

    This is the only place supervisor state survives between operator
    commands. Every field is an identifier, enum, or typed reason code —
    the record can never smuggle prose into routing decisions.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    state: SupervisorState
    plan_version: str | None = None
    draft_schedule_id: str | None = None
    approval_event_id: str | None = None
    recovery_mode: RecoveryAction | None = None
    replan_kind: ReplanKind | None = None
    reason_code: ReasonCode | None = None
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def _timestamps_aware(self) -> RunRecord:
        if self.created_at.tzinfo is None or self.updated_at.tzinfo is None:
            raise ValueError("run record timestamps must be timezone-aware")
        if self.updated_at < self.created_at:
            raise ValueError("updated_at must not precede created_at")
        return self


@runtime_checkable
class AppStateStore(Protocol):
    """Read/write surface for app-plane state."""

    def save_onboarding(self, record: OnboardingRecord) -> None: ...

    def get_onboarding(self, user_id: str) -> OnboardingRecord | None: ...

    def save_syllabus(self, user_id: str, syllabus: SyllabusUnits) -> None: ...

    def get_syllabus(self, user_id: str) -> SyllabusUnits | None: ...

    def save_draft(self, user_id: str, draft: DraftSchedule) -> None: ...

    def get_draft(self, draft_schedule_id: str) -> DraftSchedule | None: ...

    def save_run(self, record: RunRecord) -> None: ...

    def get_run(self, run_id: str) -> RunRecord | None: ...

    def list_runs_for_user(self, user_id: str) -> list[RunRecord]: ...

    def latest_run_for_user(self, user_id: str) -> RunRecord | None: ...


def _latest(runs: list[RunRecord]) -> RunRecord | None:
    """Most recently updated run; ties resolve to the latest inserted.

    Shared by both implementations so the selection rule cannot drift:
    ``sorted`` is stable, so among equal ``updated_at`` values the last
    element in insertion order wins.
    """
    if not runs:
        return None
    return sorted(runs, key=lambda r: r.updated_at)[-1]


class InMemoryAppStateStore:
    """Default test store. Thread-safe, ephemeral, non-persistent."""

    def __init__(self) -> None:
        self._onboarding: dict[str, OnboardingRecord] = {}
        self._syllabi: dict[str, SyllabusUnits] = {}
        self._drafts: dict[str, DraftSchedule] = {}
        self._runs: dict[str, RunRecord] = {}
        self._run_order: list[str] = []
        self._lock = threading.RLock()

    def save_onboarding(self, record: OnboardingRecord) -> None:
        with self._lock:
            self._onboarding[record.user_id] = record

    def get_onboarding(self, user_id: str) -> OnboardingRecord | None:
        with self._lock:
            return self._onboarding.get(user_id)

    def save_syllabus(self, user_id: str, syllabus: SyllabusUnits) -> None:
        with self._lock:
            self._syllabi[user_id] = syllabus

    def get_syllabus(self, user_id: str) -> SyllabusUnits | None:
        with self._lock:
            return self._syllabi.get(user_id)

    def save_draft(self, user_id: str, draft: DraftSchedule) -> None:
        del user_id  # kept for protocol parity; drafts are keyed by their id
        with self._lock:
            if draft.draft_schedule_id in self._drafts:
                raise DraftAlreadyExistsError(draft.draft_schedule_id)
            self._drafts[draft.draft_schedule_id] = draft

    def get_draft(self, draft_schedule_id: str) -> DraftSchedule | None:
        with self._lock:
            return self._drafts.get(draft_schedule_id)

    def save_run(self, record: RunRecord) -> None:
        with self._lock:
            if record.run_id not in self._runs:
                self._run_order.append(record.run_id)
            self._runs[record.run_id] = record

    def get_run(self, run_id: str) -> RunRecord | None:
        with self._lock:
            return self._runs.get(run_id)

    def list_runs_for_user(self, user_id: str) -> list[RunRecord]:
        with self._lock:
            return [
                self._runs[i] for i in self._run_order if self._runs[i].user_id == user_id
            ]

    def latest_run_for_user(self, user_id: str) -> RunRecord | None:
        return _latest(self.list_runs_for_user(user_id))


_SCHEMA_COMPONENT = "app.state"
_SCHEMA_VERSION = 1
_SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS app_documents (
        kind TEXT NOT NULL,
        doc_key TEXT NOT NULL,
        user_id TEXT,
        payload TEXT NOT NULL,
        PRIMARY KEY (kind, doc_key)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_app_documents_kind_user
        ON app_documents (kind, user_id)
    """,
)

_KIND_ONBOARDING = "onboarding"
_KIND_SYLLABUS = "syllabus"
_KIND_DRAFT = "draft"
_KIND_RUN = "run"


class SqliteAppStateStore:
    """Persistent twin of :class:`InMemoryAppStateStore` (Phase 9a kernel).

    One generic document table: app-plane records share a (kind, key) →
    canonical-JSON-payload shape, and reads rebuild the frozen models with
    ``model_validate_json`` so a round trip is contract-validated.
    """

    def __init__(self, db: SqliteDatabase) -> None:
        self._db = db
        db.ensure_schema(_SCHEMA_COMPONENT, version=_SCHEMA_VERSION, statements=_SCHEMA)

    def _upsert(self, kind: str, key: str, user_id: str | None, payload: str) -> None:
        with self._db.transaction() as cur:
            cur.execute(
                "INSERT INTO app_documents (kind, doc_key, user_id, payload)"
                " VALUES (?, ?, ?, ?)"
                " ON CONFLICT (kind, doc_key) DO UPDATE SET"
                " user_id = excluded.user_id, payload = excluded.payload",
                (kind, key, user_id, payload),
            )

    def _get(self, kind: str, key: str) -> str | None:
        with self._db.read() as cur:
            row = cur.execute(
                "SELECT payload FROM app_documents WHERE kind = ? AND doc_key = ?",
                (kind, key),
            ).fetchone()
        return None if row is None else str(row[0])

    def save_onboarding(self, record: OnboardingRecord) -> None:
        self._upsert(
            _KIND_ONBOARDING, record.user_id, record.user_id, record.model_dump_json()
        )

    def get_onboarding(self, user_id: str) -> OnboardingRecord | None:
        payload = self._get(_KIND_ONBOARDING, user_id)
        return None if payload is None else OnboardingRecord.model_validate_json(payload)

    def save_syllabus(self, user_id: str, syllabus: SyllabusUnits) -> None:
        self._upsert(_KIND_SYLLABUS, user_id, user_id, syllabus.model_dump_json())

    def get_syllabus(self, user_id: str) -> SyllabusUnits | None:
        payload = self._get(_KIND_SYLLABUS, user_id)
        return None if payload is None else SyllabusUnits.model_validate_json(payload)

    def save_draft(self, user_id: str, draft: DraftSchedule) -> None:
        with self._db.transaction() as cur:
            row = cur.execute(
                "SELECT 1 FROM app_documents WHERE kind = ? AND doc_key = ?",
                (_KIND_DRAFT, draft.draft_schedule_id),
            ).fetchone()
            if row is not None:
                raise DraftAlreadyExistsError(draft.draft_schedule_id)
            cur.execute(
                "INSERT INTO app_documents (kind, doc_key, user_id, payload)"
                " VALUES (?, ?, ?, ?)",
                (_KIND_DRAFT, draft.draft_schedule_id, user_id, draft.model_dump_json()),
            )

    def get_draft(self, draft_schedule_id: str) -> DraftSchedule | None:
        payload = self._get(_KIND_DRAFT, draft_schedule_id)
        return None if payload is None else DraftSchedule.model_validate_json(payload)

    def save_run(self, record: RunRecord) -> None:
        self._upsert(_KIND_RUN, record.run_id, record.user_id, record.model_dump_json())

    def get_run(self, run_id: str) -> RunRecord | None:
        payload = self._get(_KIND_RUN, run_id)
        return None if payload is None else RunRecord.model_validate_json(payload)

    def list_runs_for_user(self, user_id: str) -> list[RunRecord]:
        with self._db.read() as cur:
            rows = cur.execute(
                "SELECT payload FROM app_documents"
                " WHERE kind = ? AND user_id = ? ORDER BY rowid",
                (_KIND_RUN, user_id),
            ).fetchall()
        return [RunRecord.model_validate_json(row[0]) for row in rows]

    def latest_run_for_user(self, user_id: str) -> RunRecord | None:
        return _latest(self.list_runs_for_user(user_id))
