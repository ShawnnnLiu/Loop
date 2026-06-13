"""Tests for the ``AppStateStore`` implementations (Phase 9b).

The behavioral suite is parametrized over the in-memory and SQLite
implementations (Phase 9a kernel): both must satisfy the protocol
identically. Restart-survival tests at the bottom are SQLite-only by nature.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from agentic_calendar.app.state import (
    AppStateStore,
    DraftAlreadyExistsError,
    InMemoryAppStateStore,
    OnboardingRecord,
    RunRecord,
    SqliteAppStateStore,
)
from agentic_calendar.common.sqlite import SqliteDatabase
from agentic_calendar.contracts.draft_schedule import DraftSchedule, DraftScheduleEntry
from agentic_calendar.contracts.syllabus_units import SyllabusUnits
from agentic_calendar.supervisor.state import SupervisorState
from agentic_calendar.tools.llm_smoke import sample_fixture_inputs

_T0 = datetime(2026, 6, 11, 12, 0, 0, tzinfo=UTC)


@pytest.fixture(params=["in_memory", "sqlite"])
def store(request: pytest.FixtureRequest, tmp_path: Path) -> AppStateStore:
    if request.param == "sqlite":
        return SqliteAppStateStore(SqliteDatabase(tmp_path / "store.db"))
    return InMemoryAppStateStore()


def _onboarding(*, timezone: str = "America/Los_Angeles") -> OnboardingRecord:
    profile, _, _ = sample_fixture_inputs()
    return OnboardingRecord(
        user_id=profile.user_id,
        user_profile=profile,
        timezone=timezone,
        motivation_profile=None,
        created_at=_T0,
        updated_at=_T0,
    )


def _syllabus() -> SyllabusUnits:
    _, syllabus, _ = sample_fixture_inputs()
    return syllabus


def _draft(draft_schedule_id: str = "draft_001") -> DraftSchedule:
    return DraftSchedule(
        draft_schedule_id=draft_schedule_id,
        plan_version="plan_001",
        entries=(
            DraftScheduleEntry(
                task_id="dp_001",
                start=_T0,
                end=_T0 + timedelta(minutes=60),
            ),
        ),
        created_at=_T0,
    )


def _run(
    *,
    run_id: str = "run_001",
    user_id: str = "user_smoke",
    state: SupervisorState = SupervisorState.AWAITING_USER_APPROVAL,
    created_at: datetime = _T0,
    updated_at: datetime | None = None,
) -> RunRecord:
    return RunRecord(
        run_id=run_id,
        user_id=user_id,
        state=state,
        created_at=created_at,
        updated_at=created_at if updated_at is None else updated_at,
    )


# --------------------------------------------------------------------------- #
# Protocol
# --------------------------------------------------------------------------- #


def test_satisfies_protocol(store: AppStateStore) -> None:
    """Both implementations structurally satisfy the runtime-checkable protocol."""
    assert isinstance(store, AppStateStore)


# --------------------------------------------------------------------------- #
# Onboarding
# --------------------------------------------------------------------------- #


def test_onboarding_save_and_get_round_trip(store: AppStateStore) -> None:
    """A stored onboarding bundle is recovered exactly (contract-validated)."""
    record = _onboarding()
    store.save_onboarding(record)
    assert store.get_onboarding(record.user_id) == record


def test_get_onboarding_missing_returns_none(store: AppStateStore) -> None:
    """An unknown user has no onboarding record — None, not an error."""
    assert store.get_onboarding("user_missing") is None


def test_onboarding_save_is_upsert(store: AppStateStore) -> None:
    """Re-onboarding the same user replaces the bundle: the second save wins."""
    first = _onboarding(timezone="America/Los_Angeles")
    second = OnboardingRecord.model_validate(first.model_dump() | {"timezone": "UTC"})
    store.save_onboarding(first)
    store.save_onboarding(second)
    got = store.get_onboarding(first.user_id)
    assert got == second
    assert got is not None and got.timezone == "UTC"


def test_onboarding_record_rejects_unknown_timezone() -> None:
    """``timezone`` must resolve as an IANA zone — bad input fails validation."""
    with pytest.raises(ValidationError, match="unknown IANA timezone"):
        _onboarding(timezone="Not/AZone")


def test_onboarding_record_rejects_mismatched_user_id() -> None:
    """The record's user_id must match the embedded profile's user_id."""
    profile, _, _ = sample_fixture_inputs()
    with pytest.raises(ValidationError, match="must match onboarding user_id"):
        OnboardingRecord(
            user_id="user_other",
            user_profile=profile,
            timezone="UTC",
            created_at=_T0,
            updated_at=_T0,
        )


# --------------------------------------------------------------------------- #
# Syllabus
# --------------------------------------------------------------------------- #


def test_syllabus_save_and_get_round_trip(store: AppStateStore) -> None:
    """The validated syllabus a replan re-enters with is recovered exactly."""
    syllabus = _syllabus()
    store.save_syllabus("user_smoke", syllabus)
    assert store.get_syllabus("user_smoke") == syllabus


def test_get_syllabus_missing_returns_none(store: AppStateStore) -> None:
    """A user without a stored syllabus reads back as None."""
    assert store.get_syllabus("user_missing") is None


def test_syllabus_save_is_upsert(store: AppStateStore) -> None:
    """Saving a new syllabus for the same user replaces the previous one."""
    first = _syllabus()
    second = SyllabusUnits.model_validate(
        first.model_dump() | {"goal_summary": "Revised goal summary for the replan."}
    )
    store.save_syllabus("user_smoke", first)
    store.save_syllabus("user_smoke", second)
    assert store.get_syllabus("user_smoke") == second


# --------------------------------------------------------------------------- #
# Drafts
# --------------------------------------------------------------------------- #


def test_draft_save_and_get_round_trip(store: AppStateStore) -> None:
    """A stored draft is recovered exactly — the approval hash depends on it."""
    draft = _draft()
    store.save_draft("user_smoke", draft)
    assert store.get_draft(draft.draft_schedule_id) == draft


def test_get_draft_missing_returns_none(store: AppStateStore) -> None:
    """An unknown draft_schedule_id reads back as None."""
    assert store.get_draft("draft_missing") is None


def test_duplicate_draft_schedule_id_raises(store: AppStateStore) -> None:
    """Drafts are immutable once produced: replacing one in place would
    silently invalidate a pending approval hash (axiom 06)."""
    store.save_draft("user_smoke", _draft())
    with pytest.raises(DraftAlreadyExistsError):
        store.save_draft("user_smoke", _draft())


# --------------------------------------------------------------------------- #
# Runs
# --------------------------------------------------------------------------- #


def test_run_save_and_get_round_trip(store: AppStateStore) -> None:
    """A persisted run record (the only surviving supervisor state) round-trips."""
    run = _run()
    store.save_run(run)
    assert store.get_run(run.run_id) == run


def test_get_run_missing_returns_none(store: AppStateStore) -> None:
    """An unknown run_id reads back as None."""
    assert store.get_run("run_missing") is None


def test_run_save_is_upsert_by_run_id(store: AppStateStore) -> None:
    """Saving the same run_id again replaces the record — one row per run."""
    initial = _run(state=SupervisorState.AWAITING_USER_APPROVAL)
    updated = _run(
        state=SupervisorState.CALENDAR_WRITE_APPROVED,
        updated_at=_T0 + timedelta(minutes=5),
    )
    store.save_run(initial)
    store.save_run(updated)
    assert store.get_run("run_001") == updated
    assert store.list_runs_for_user("user_smoke") == [updated]


def test_list_runs_for_user_insertion_order_and_isolation(
    store: AppStateStore,
) -> None:
    """Listing preserves insertion order and never leaks another user's runs."""
    run_a = _run(run_id="run_a", user_id="user_smoke")
    run_b = _run(run_id="run_b", user_id="user_smoke")
    run_c = _run(run_id="run_c", user_id="user_other")
    store.save_run(run_a)
    store.save_run(run_b)
    store.save_run(run_c)
    assert store.list_runs_for_user("user_smoke") == [run_a, run_b]
    assert store.list_runs_for_user("user_other") == [run_c]


def test_latest_run_for_user_is_most_recently_updated(store: AppStateStore) -> None:
    """``latest_run_for_user`` selects by updated_at, not by insertion order.

    An older run that receives a newer transition becomes the latest again —
    the next CLI invocation must resume from where the supervisor actually is.
    """
    run_a = _run(run_id="run_a", created_at=_T0)
    run_b = _run(run_id="run_b", created_at=_T0 + timedelta(hours=1))
    store.save_run(run_a)
    store.save_run(run_b)
    latest = store.latest_run_for_user("user_smoke")
    assert latest is not None and latest.run_id == "run_b"

    run_a_updated = _run(
        run_id="run_a", created_at=_T0, updated_at=_T0 + timedelta(hours=2)
    )
    store.save_run(run_a_updated)
    latest = store.latest_run_for_user("user_smoke")
    assert latest is not None and latest.run_id == "run_a"
    assert latest == run_a_updated


def test_latest_run_for_unknown_user_returns_none(store: AppStateStore) -> None:
    """A user with no runs has no latest run."""
    assert store.latest_run_for_user("user_missing") is None


# --------------------------------------------------------------------------- #
# Restart survival (SQLite-only by nature): state written before a process
# exit must be fully recovered by a fresh store instance on the same file.
# --------------------------------------------------------------------------- #


def test_sqlite_state_survives_restart(tmp_path: Path) -> None:
    """Every app-plane record kind written before close is recovered exactly
    by a fresh store on the same path — the property the cycle CLI relies on."""
    db_path = tmp_path / "store.db"
    db = SqliteDatabase(db_path)
    first = SqliteAppStateStore(db)
    onboarding = _onboarding()
    syllabus = _syllabus()
    draft = _draft()
    run = _run(user_id=onboarding.user_id)
    first.save_onboarding(onboarding)
    first.save_syllabus(onboarding.user_id, syllabus)
    first.save_draft(onboarding.user_id, draft)
    first.save_run(run)
    db.close()

    reopened = SqliteAppStateStore(SqliteDatabase(db_path))
    assert reopened.get_onboarding(onboarding.user_id) == onboarding
    assert reopened.get_syllabus(onboarding.user_id) == syllabus
    assert reopened.get_draft(draft.draft_schedule_id) == draft
    assert reopened.get_run(run.run_id) == run
    assert reopened.list_runs_for_user(onboarding.user_id) == [run]
    assert reopened.latest_run_for_user(onboarding.user_id) == run
