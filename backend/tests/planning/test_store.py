"""Tests for ``planning.store.InMemoryPlanVersionStore``."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from agentic_calendar.contracts.task_plan import TaskPlan
from agentic_calendar.planning.plan_version import LifecycleState, PlanVersion
from agentic_calendar.planning.store import (
    InMemoryPlanVersionStore,
    MultipleActivePlansError,
    PlanVersionNotFoundError,
    PlanVersionStore,
)
from tests._fixture_loader import iter_valid


def _make_pv(
    *,
    plan_version: str,
    user_id: str = "user_001",
    state: LifecycleState = LifecycleState.DRAFT,
    parent: str | None = None,
) -> PlanVersion:
    base = TaskPlan.model_validate(next(iter_valid("task_plan")).payload)
    plan = base.model_copy(update={"plan_version": plan_version})
    now = datetime(2026, 5, 4, 12, 0, 0, tzinfo=UTC)
    return PlanVersion(
        plan_version=plan_version,
        user_id=user_id,
        parent_plan_version=parent,
        state=state,
        plan=plan,
        created_at=now,
        updated_at=now,
    )


def test_satisfies_protocol() -> None:
    assert isinstance(InMemoryPlanVersionStore(), PlanVersionStore)


def test_save_and_get_round_trip() -> None:
    store = InMemoryPlanVersionStore()
    pv = _make_pv(plan_version="plan_001")
    store.save(pv)
    got = store.get("user_001", "plan_001")
    assert got is pv


def test_get_missing_raises() -> None:
    store = InMemoryPlanVersionStore()
    with pytest.raises(PlanVersionNotFoundError):
        store.get("user_001", "missing")


def test_list_returns_all_for_user_in_creation_order() -> None:
    store = InMemoryPlanVersionStore()
    pv1 = _make_pv(plan_version="plan_001")
    pv2 = _make_pv(plan_version="plan_002")
    store.save(pv1)
    store.save(pv2)
    listing = store.list_for_user("user_001")
    assert [pv.plan_version for pv in listing] == ["plan_001", "plan_002"]


def test_get_active_returns_none_when_no_active() -> None:
    store = InMemoryPlanVersionStore()
    store.save(_make_pv(plan_version="plan_001"))
    assert store.get_active("user_001") is None


def test_get_active_returns_active_plan() -> None:
    store = InMemoryPlanVersionStore()
    pv = _make_pv(plan_version="plan_001", state=LifecycleState.ACTIVE)
    store.save(pv)
    assert store.get_active("user_001") is pv


def test_two_active_plans_for_same_user_raises_invariant() -> None:
    store = InMemoryPlanVersionStore()
    store.save(_make_pv(plan_version="plan_001", state=LifecycleState.ACTIVE))
    with pytest.raises(MultipleActivePlansError):
        store.save(_make_pv(plan_version="plan_002", state=LifecycleState.ACTIVE))


def test_failed_active_save_rolls_back_and_leaves_store_queryable() -> None:
    """A save that violates the single-active invariant must not corrupt state.

    Without rollback, the rejected plan would linger in the bucket and the
    next ``get_active`` call would also raise — leaving the store unusable.
    """
    store = InMemoryPlanVersionStore()
    pv1 = _make_pv(plan_version="plan_001", state=LifecycleState.ACTIVE)
    pv2 = _make_pv(plan_version="plan_002", state=LifecycleState.ACTIVE)
    store.save(pv1)
    with pytest.raises(MultipleActivePlansError):
        store.save(pv2)
    # The rejected plan must not be present.
    with pytest.raises(PlanVersionNotFoundError):
        store.get("user_001", "plan_002")
    # The store is still queryable; the original active plan is intact.
    active = store.get_active("user_001")
    assert active is not None
    assert active.plan_version == "plan_001"


def test_failed_save_restores_prior_version_when_replacing() -> None:
    """If a same-id save would violate the invariant, the prior value must remain."""
    store = InMemoryPlanVersionStore()
    pv_active = _make_pv(plan_version="plan_001", state=LifecycleState.ACTIVE)
    other_active = _make_pv(plan_version="plan_other", state=LifecycleState.ACTIVE)
    store.save(pv_active)
    with pytest.raises(MultipleActivePlansError):
        store.save(other_active)
    # plan_001 still present, still ACTIVE.
    survivor = store.get("user_001", "plan_001")
    assert survivor.state is LifecycleState.ACTIVE


def test_users_are_isolated() -> None:
    store = InMemoryPlanVersionStore()
    pv_a = _make_pv(plan_version="plan_a", user_id="user_A")
    pv_b = _make_pv(plan_version="plan_b", user_id="user_B")
    store.save(pv_a)
    store.save(pv_b)
    assert store.list_for_user("user_A") == [pv_a]
    assert store.list_for_user("user_B") == [pv_b]
    with pytest.raises(PlanVersionNotFoundError):
        store.get("user_A", "plan_b")


def test_save_replaces_same_id_with_updated_version() -> None:
    """Saving a model_copy with the same id is permitted (e.g. transitions)."""
    store = InMemoryPlanVersionStore()
    pv = _make_pv(plan_version="plan_001")
    store.save(pv)
    now = datetime(2026, 5, 5, 12, 0, 0, tzinfo=UTC)
    approved = pv.transition_to(LifecycleState.APPROVED, now=now)
    store.save(approved)
    assert store.get("user_001", "plan_001").state is LifecycleState.APPROVED


# --------------------------------------------------------------------------- #
# Concurrency: the in-memory store advertises thread-safety via an RLock; the
# tests below pin that contract so a future refactor cannot quietly drop it.
# --------------------------------------------------------------------------- #


def test_concurrent_saves_of_distinct_plan_versions_all_visible() -> None:
    """N threads saving distinct plan_versions: every save is visible after join."""
    import threading

    store = InMemoryPlanVersionStore()
    n = 64
    pvs = [_make_pv(plan_version=f"plan_{i:03d}") for i in range(n)]
    barrier = threading.Barrier(n)

    def saver(pv: PlanVersion) -> None:
        barrier.wait()  # release all threads simultaneously
        store.save(pv)

    threads = [threading.Thread(target=saver, args=(pv,)) for pv in pvs]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    listing = store.list_for_user("user_001")
    assert {pv.plan_version for pv in listing} == {f"plan_{i:03d}" for i in range(n)}


def test_concurrent_active_saves_exactly_one_wins() -> None:
    """Two threads racing to mark different plans ACTIVE for the same user.

    The single-active invariant must hold: exactly one save succeeds; the
    other raises ``MultipleActivePlansError``.
    """
    import threading

    store = InMemoryPlanVersionStore()
    pv1 = _make_pv(plan_version="plan_001", state=LifecycleState.ACTIVE)
    pv2 = _make_pv(plan_version="plan_002", state=LifecycleState.ACTIVE)

    errors: list[BaseException] = []
    successes: list[str] = []
    barrier = threading.Barrier(2)
    lock = threading.Lock()

    def saver(pv: PlanVersion) -> None:
        barrier.wait()
        try:
            store.save(pv)
        except MultipleActivePlansError as exc:
            with lock:
                errors.append(exc)
        else:
            with lock:
                successes.append(pv.plan_version)

    threads = [threading.Thread(target=saver, args=(pv,)) for pv in (pv1, pv2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(successes) == 1
    assert len(errors) == 1
    active = store.get_active("user_001")
    assert active is not None
    assert active.plan_version == successes[0]
