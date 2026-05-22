"""In-memory plan-version store (Phase 1).

The store is the only object that owns the mapping from
``(user_id, plan_version)`` to a ``PlanVersion`` and the *current* "active"
plan per user. Persistence-backed implementations land in later phases; the
Phase 1 in-memory version is sufficient for golden tests and the supervisor
state machine.

Concurrency: the in-memory store uses a single threading lock around every
mutation so two coroutines / threads cannot observe a torn write. Distributed
locking arrives with the Postgres-backed store in a later phase.
"""

from __future__ import annotations

import threading
from typing import Protocol, runtime_checkable

from agentic_calendar.common.errors import AgenticCalendarError

from .plan_version import LifecycleState, PlanVersion


class PlanVersionStoreError(AgenticCalendarError):
    """Base for plan-store errors that callers may catch."""


class PlanVersionAlreadyExistsError(PlanVersionStoreError):
    pass


class PlanVersionNotFoundError(PlanVersionStoreError):
    pass


class MultipleActivePlansError(PlanVersionStoreError):
    """Invariant breach: a user had >1 plan in ``ACTIVE`` state."""


@runtime_checkable
class PlanVersionStore(Protocol):
    """Read/write surface for plan versions."""

    def save(self, plan_version: PlanVersion) -> None: ...

    def get(self, user_id: str, plan_version: str) -> PlanVersion: ...

    def list_for_user(self, user_id: str) -> list[PlanVersion]: ...

    def get_active(self, user_id: str) -> PlanVersion | None: ...


class InMemoryPlanVersionStore:
    """Default Phase 1 store. Thread-safe, ephemeral, non-persistent."""

    def __init__(self) -> None:
        self._by_user: dict[str, dict[str, PlanVersion]] = {}
        self._lock = threading.RLock()

    def save(self, plan_version: PlanVersion) -> None:
        """Insert or replace by ``(user_id, plan_version)``.

        State transitions arrive as ``model_copy`` instances of the same id;
        the store accepts these idempotently. The single-active invariant is
        re-checked on every save; if the new write would violate it, the
        store rolls back the mutation and re-raises so the caller sees a
        clean failure rather than a corrupt bucket.
        """
        with self._lock:
            user_bucket = self._by_user.setdefault(plan_version.user_id, {})
            prior = user_bucket.get(plan_version.plan_version)
            user_bucket[plan_version.plan_version] = plan_version
            try:
                self._enforce_single_active(plan_version.user_id)
            except MultipleActivePlansError:
                # Roll back so the store stays in a queryable state.
                if prior is None:
                    del user_bucket[plan_version.plan_version]
                else:
                    user_bucket[plan_version.plan_version] = prior
                raise

    def get(self, user_id: str, plan_version: str) -> PlanVersion:
        with self._lock:
            user_bucket = self._by_user.get(user_id, {})
            if plan_version not in user_bucket:
                raise PlanVersionNotFoundError(plan_version)
            return user_bucket[plan_version]

    def list_for_user(self, user_id: str) -> list[PlanVersion]:
        with self._lock:
            return sorted(
                self._by_user.get(user_id, {}).values(),
                key=lambda pv: pv.created_at,
            )

    def get_active(self, user_id: str) -> PlanVersion | None:
        with self._lock:
            actives = [
                pv
                for pv in self._by_user.get(user_id, {}).values()
                if pv.state is LifecycleState.ACTIVE
            ]
            if len(actives) > 1:
                raise MultipleActivePlansError(user_id)
            return actives[0] if actives else None

    def _enforce_single_active(self, user_id: str) -> None:
        actives = [
            pv
            for pv in self._by_user[user_id].values()
            if pv.state is LifecycleState.ACTIVE
        ]
        if len(actives) > 1:
            raise MultipleActivePlansError(user_id)
