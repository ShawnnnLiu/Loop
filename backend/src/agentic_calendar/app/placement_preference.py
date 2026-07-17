"""Placement-preference observation stores (axiom 05 "Revealed-preference term").

Append-only journal of the user actions that state a preferred
time-of-day — drag-to-adjust moves and inbound reconciliation adoptions
(``docs/specs/placement-preference.schema.md``). Rows are per observation,
never pre-aggregated: the recency window and count threshold are a pure
read-time computation in the app layer's evidence composition, so the
journaled tuning knobs (``revealed_window_days`` /
``revealed_min_observations``) can move without a data migration.

Observations are immutable facts: a duplicate ``observation_id`` always
rejects the append (the threshold-change-log invariant). ``delete_for_user``
exists solely for the data-control surface (view / export / delete one
user's data) and is the only removal path.
"""

from __future__ import annotations

import threading
from typing import Protocol, runtime_checkable

from agentic_calendar.common.errors import AgenticCalendarError
from agentic_calendar.common.sqlite import SqliteDatabase
from agentic_calendar.contracts.placement_preference import (
    PlacementPreferenceObservation,
)


class PlacementPreferenceStoreError(AgenticCalendarError):
    """Base for placement-preference store errors that callers may catch."""


class PlacementPreferenceAlreadyExistsError(PlacementPreferenceStoreError):
    """Attempted to append an ``observation_id`` that already exists.

    The journal is append-only: rewriting an observation would silently
    rewrite the revealed-preference evidence the scheduler serves from.
    """


@runtime_checkable
class PlacementPreferenceStore(Protocol):
    """Append-only read/write surface for placement-preference observations."""

    def append(self, observation: PlacementPreferenceObservation) -> None: ...

    def list_for_user(self, user_id: str) -> list[PlacementPreferenceObservation]: ...

    def delete_for_user(self, user_id: str) -> int: ...


class InMemoryPlacementPreferenceStore:
    """Default test store. Thread-safe, ephemeral, non-persistent."""

    def __init__(self) -> None:
        self._observations: dict[str, PlacementPreferenceObservation] = {}
        self._order: list[str] = []
        self._lock = threading.RLock()

    def append(self, observation: PlacementPreferenceObservation) -> None:
        with self._lock:
            if observation.observation_id in self._observations:
                raise PlacementPreferenceAlreadyExistsError(
                    observation.observation_id
                )
            self._observations[observation.observation_id] = observation
            self._order.append(observation.observation_id)

    def list_for_user(self, user_id: str) -> list[PlacementPreferenceObservation]:
        with self._lock:
            return [
                self._observations[observation_id]
                for observation_id in self._order
                if self._observations[observation_id].user_id == user_id
            ]

    def delete_for_user(self, user_id: str) -> int:
        with self._lock:
            doomed = [
                observation_id
                for observation_id in self._order
                if self._observations[observation_id].user_id == user_id
            ]
            for observation_id in doomed:
                del self._observations[observation_id]
            self._order = [
                observation_id
                for observation_id in self._order
                if observation_id not in set(doomed)
            ]
            return len(doomed)


_SCHEMA_COMPONENT = "app.placement_preferences"
_SCHEMA_VERSION = 1
_SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS placement_preference_observations (
        observation_id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        payload TEXT NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_placement_preference_observations_user
        ON placement_preference_observations (user_id)
    """,
)


class SqlitePlacementPreferenceStore:
    """Persistent twin of :class:`InMemoryPlacementPreferenceStore`.

    Rows hold the canonical Pydantic JSON dump plus the ``user_id`` lookup
    column; reads rebuild the frozen model with ``model_validate_json`` so a
    round trip is contract-validated, never trusted. The duplicate check is
    an explicit SELECT inside the insert transaction so the error stays the
    typed :class:`PlacementPreferenceAlreadyExistsError`, never a leaked
    ``sqlite3.IntegrityError``.
    """

    def __init__(self, db: SqliteDatabase) -> None:
        self._db = db
        db.ensure_schema(_SCHEMA_COMPONENT, version=_SCHEMA_VERSION, statements=_SCHEMA)

    def append(self, observation: PlacementPreferenceObservation) -> None:
        with self._db.transaction() as cur:
            row = cur.execute(
                "SELECT 1 FROM placement_preference_observations"
                " WHERE observation_id = ?",
                (observation.observation_id,),
            ).fetchone()
            if row is not None:
                raise PlacementPreferenceAlreadyExistsError(
                    observation.observation_id
                )
            cur.execute(
                "INSERT INTO placement_preference_observations"
                " (observation_id, user_id, payload)"
                " VALUES (?, ?, ?)",
                (
                    observation.observation_id,
                    observation.user_id,
                    observation.model_dump_json(),
                ),
            )

    def list_for_user(self, user_id: str) -> list[PlacementPreferenceObservation]:
        # Insertion order (rowid) — the same ordering contract as the
        # in-memory store's append list.
        with self._db.read() as cur:
            rows = cur.execute(
                "SELECT payload FROM placement_preference_observations"
                " WHERE user_id = ? ORDER BY rowid",
                (user_id,),
            ).fetchall()
        return [
            PlacementPreferenceObservation.model_validate_json(row[0]) for row in rows
        ]

    def delete_for_user(self, user_id: str) -> int:
        with self._db.transaction() as cur:
            cur.execute(
                "DELETE FROM placement_preference_observations WHERE user_id = ?",
                (user_id,),
            )
            return cur.rowcount
