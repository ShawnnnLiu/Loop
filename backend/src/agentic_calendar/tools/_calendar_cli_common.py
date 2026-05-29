"""Shared wiring for the Phase 2 calendar operator CLIs.

The five calendar CLIs (``preview_calendar_write``, ``approve_calendar_write``,
``write_calendar``, ``verify_calendar``, ``rollback_calendar``) all need the
same deterministic setup: a :class:`FrozenClock`, a
:class:`DeterministicIdGenerator`, an :class:`InMemoryCalendarAdapter`, and the
two in-memory stores. This helper builds them all so each CLI focuses only on
its own behavior.

Because the Phase 2 stores are in-process, the verify/rollback CLIs cannot
look up a run_id from a prior invocation. They instead accept ``--scenario``
and run the full preview→approve→write flow first to populate state, then
exercise the relevant operation. That mirrors how the Phase 1 ``visualize``
CLI bakes the scenario into a single invocation.

Determinism: every CLI calls :func:`make_environment` with the same fixed
instant + scenario, so stdout snapshots are byte-stable.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from agentic_calendar.approval.store import InMemoryApprovalEventStore
from agentic_calendar.calendar_writer import (
    CalendarWriteLockManager,
    CalendarWriteManager,
    FailureModes,
    InMemoryCalendarAdapter,
    InMemoryCalendarEventMappingStore,
)
from agentic_calendar.common.clock import FrozenClock
from agentic_calendar.common.ids import DeterministicIdGenerator
from agentic_calendar.contracts.approval_event import (
    ApprovalActionType,
    ApprovalEvent,
    HashAlgorithm,
)
from agentic_calendar.contracts.draft_schedule import DraftSchedule
from agentic_calendar.contracts.hashing import canonical_payload_hash
from agentic_calendar.scheduler import schedule

from .visualize import SCENARIOS

DEFAULT_FROZEN_INSTANT = datetime(2026, 5, 4, 17, 55, tzinfo=UTC)
"""Pinned clock so CLI output is byte-stable across runs."""

DEFAULT_USER_ID = "user_demo"
DEFAULT_TARGET_CALENDAR_ID = "primary"
DEFAULT_APPROVAL_TTL = timedelta(hours=24)


@dataclass(frozen=True, slots=True)
class CalendarCliEnvironment:
    """Wired-up adapter, stores, lock, and manager — ready to use."""

    clock: FrozenClock
    id_generator: DeterministicIdGenerator
    adapter: InMemoryCalendarAdapter
    mapping_store: InMemoryCalendarEventMappingStore
    approval_store: InMemoryApprovalEventStore
    lock_manager: CalendarWriteLockManager
    manager: CalendarWriteManager


def make_environment(
    *,
    failure_modes: FailureModes | None = None,
    frozen_instant: datetime = DEFAULT_FROZEN_INSTANT,
) -> CalendarCliEnvironment:
    """Build a fresh deterministic environment for one CLI invocation."""
    clock = FrozenClock(frozen_instant)
    id_generator = DeterministicIdGenerator()
    adapter = InMemoryCalendarAdapter(
        id_generator=id_generator, failure_modes=failure_modes
    )
    mapping_store = InMemoryCalendarEventMappingStore()
    approval_store = InMemoryApprovalEventStore()
    lock_manager = CalendarWriteLockManager(clock=clock)
    manager = CalendarWriteManager(
        adapter=adapter,
        mapping_store=mapping_store,
        approval_store=approval_store,
        lock_manager=lock_manager,
        id_generator=id_generator,
        clock=clock,
    )
    return CalendarCliEnvironment(
        clock=clock,
        id_generator=id_generator,
        adapter=adapter,
        mapping_store=mapping_store,
        approval_store=approval_store,
        lock_manager=lock_manager,
        manager=manager,
    )


def build_draft_for_scenario(
    scenario_name: str, env: CalendarCliEnvironment
) -> DraftSchedule:
    """Run the Phase 1 scheduler on ``scenario_name`` and assemble a draft.

    Raises ``KeyError`` if ``scenario_name`` is unknown and ``ValueError`` if
    the scheduler output is FAILED (no draft is possible).
    """
    if scenario_name not in SCENARIOS:
        raise KeyError(
            f"unknown scenario {scenario_name!r}; available: "
            f"{sorted(SCENARIOS.keys())!r}"
        )
    scheduler_input = SCENARIOS[scenario_name].build()
    output = schedule(scheduler_input)
    draft_schedule_id = env.id_generator.new_id("draft")
    return DraftSchedule.from_scheduler_output(
        output,
        draft_schedule_id=draft_schedule_id,
        created_at=env.clock.now(),
    )


def create_approval(
    draft: DraftSchedule,
    env: CalendarCliEnvironment,
    *,
    user_id: str = DEFAULT_USER_ID,
    ttl: timedelta = DEFAULT_APPROVAL_TTL,
) -> ApprovalEvent:
    """Build, store, and return a fresh ``ApprovalEvent`` for ``draft``."""
    now = env.clock.now()
    approval = ApprovalEvent(
        approval_event_id=env.id_generator.new_id("approval"),
        user_id=user_id,
        plan_id=draft.plan_version,
        draft_schedule_id=draft.draft_schedule_id,
        action_type=ApprovalActionType.ADD_TO_CALENDAR,
        approved_payload_hash=canonical_payload_hash(draft, "v1"),
        hash_algorithm=HashAlgorithm.SHA256,
        hash_canonicalization_version="v1",
        created_at=now,
        expires_at=now + ttl,
    )
    env.approval_store.save(approval)
    return approval


def list_scenario_names() -> list[str]:
    """Return scenario names that produce a non-failed scheduler output."""
    return sorted(SCENARIOS.keys())
