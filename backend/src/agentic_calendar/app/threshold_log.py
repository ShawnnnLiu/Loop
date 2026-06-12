"""Threshold-change-log stores (axiom 07 "Threshold Change Log").

Append-only journal of every tuning-value change, keyed by ``change_id``
(``docs/specs/threshold-change-log.schema.md``). The latest entry for a
``(config_section, threshold_field)`` pair is its effective override, so a
deterministic replay of insertion order reproduces the effective
configuration — that replay is what ``app/tuning.py`` and the
``show_thresholds`` CLI rely on.

Entries are immutable audit facts, never edited: a duplicate ``change_id``
always rejects the append (the same invariant as the llm-call-log store).
The tuning loader is the only supported writer; nothing at runtime routes on
this log.
"""

from __future__ import annotations

import threading
from typing import Protocol, runtime_checkable

from agentic_calendar.common.errors import AgenticCalendarError
from agentic_calendar.common.sqlite import SqliteDatabase
from agentic_calendar.contracts.threshold_change_log import ThresholdChange


class ThresholdChangeLogStoreError(AgenticCalendarError):
    """Base for threshold-change-log store errors that callers may catch."""


class ThresholdChangeAlreadyExistsError(ThresholdChangeLogStoreError):
    """Attempted to append a ``change_id`` that already exists.

    The journal is append-only: rewriting an entry would silently rewrite
    audit history (axiom 07 "No silent threshold changes").
    """


@runtime_checkable
class ThresholdChangeLogStore(Protocol):
    """Append-only read/write surface for the threshold change journal."""

    def append(self, change: ThresholdChange) -> None: ...

    def list_all(self) -> list[ThresholdChange]: ...

    def list_for_field(
        self, config_section: str, threshold_field: str
    ) -> list[ThresholdChange]: ...


class InMemoryThresholdChangeLogStore:
    """Default test store. Thread-safe, ephemeral, non-persistent."""

    def __init__(self) -> None:
        self._changes: dict[str, ThresholdChange] = {}
        self._order: list[str] = []
        self._lock = threading.RLock()

    def append(self, change: ThresholdChange) -> None:
        with self._lock:
            if change.change_id in self._changes:
                raise ThresholdChangeAlreadyExistsError(change.change_id)
            self._changes[change.change_id] = change
            self._order.append(change.change_id)

    def list_all(self) -> list[ThresholdChange]:
        with self._lock:
            return [self._changes[change_id] for change_id in self._order]

    def list_for_field(
        self, config_section: str, threshold_field: str
    ) -> list[ThresholdChange]:
        with self._lock:
            return [
                self._changes[change_id]
                for change_id in self._order
                if self._changes[change_id].config_section == config_section
                and self._changes[change_id].threshold_field == threshold_field
            ]


_SCHEMA_COMPONENT = "app.threshold_changes"
_SCHEMA_VERSION = 1
_SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS threshold_changes (
        change_id TEXT PRIMARY KEY,
        config_section TEXT NOT NULL,
        threshold_field TEXT NOT NULL,
        payload TEXT NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_threshold_changes_field
        ON threshold_changes (config_section, threshold_field)
    """,
)


class SqliteThresholdChangeLogStore:
    """Persistent twin of :class:`InMemoryThresholdChangeLogStore` (Phase 9a).

    Rows hold the canonical Pydantic JSON dump plus the lookup columns; reads
    rebuild the frozen model with ``model_validate_json`` so a round trip is
    contract-validated, never trusted. The duplicate check is an explicit
    SELECT inside the insert transaction so the error stays the typed
    :class:`ThresholdChangeAlreadyExistsError`, never a leaked
    ``sqlite3.IntegrityError``.
    """

    def __init__(self, db: SqliteDatabase) -> None:
        self._db = db
        db.ensure_schema(_SCHEMA_COMPONENT, version=_SCHEMA_VERSION, statements=_SCHEMA)

    def append(self, change: ThresholdChange) -> None:
        with self._db.transaction() as cur:
            row = cur.execute(
                "SELECT 1 FROM threshold_changes WHERE change_id = ?",
                (change.change_id,),
            ).fetchone()
            if row is not None:
                raise ThresholdChangeAlreadyExistsError(change.change_id)
            cur.execute(
                "INSERT INTO threshold_changes"
                " (change_id, config_section, threshold_field, payload)"
                " VALUES (?, ?, ?, ?)",
                (
                    change.change_id,
                    change.config_section,
                    change.threshold_field,
                    change.model_dump_json(),
                ),
            )

    def list_all(self) -> list[ThresholdChange]:
        # Insertion order (rowid) — the same ordering contract as the
        # in-memory store's append list.
        with self._db.read() as cur:
            rows = cur.execute(
                "SELECT payload FROM threshold_changes ORDER BY rowid"
            ).fetchall()
        return [ThresholdChange.model_validate_json(row[0]) for row in rows]

    def list_for_field(
        self, config_section: str, threshold_field: str
    ) -> list[ThresholdChange]:
        with self._db.read() as cur:
            rows = cur.execute(
                "SELECT payload FROM threshold_changes"
                " WHERE config_section = ? AND threshold_field = ?"
                " ORDER BY rowid",
                (config_section, threshold_field),
            ).fetchall()
        return [ThresholdChange.model_validate_json(row[0]) for row in rows]
