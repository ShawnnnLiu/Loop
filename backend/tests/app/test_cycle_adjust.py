"""Integration tests for ``CycleService.adjust`` (drag-to-adjust, pre-approval).

Reuses the fixture-backed harness in ``test_cycle.py``. The canonical propose
places two tasks: ``dp_001`` Mon 2026-05-04 18:00-19:00 (60m, no deps) and
``dp_002`` Wed 2026-05-06 19:00-20:30 (90m, depends on dp_001), with the profile
allowing 08:00-22:30, weekends, and 180m/day. ``now`` is Mon 2026-05-04 12:00Z.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from agentic_calendar.app.cycle import CycleError
from agentic_calendar.contracts.common_types import TaskCategory
from agentic_calendar.contracts.placement_preference import PlacementPreferenceSource
from agentic_calendar.contracts.pooled_duration_model import TimeOfDayBand
from agentic_calendar.contracts.reason_codes import ReasonCode
from agentic_calendar.scheduler.adjustment import DraftAdjustment
from agentic_calendar.supervisor.state import SupervisorState as S
from tests.app.test_cycle import USER_ID, make_service


def _move(task_id: str, start: datetime) -> DraftAdjustment:
    return DraftAdjustment(task_id=task_id, start=start)


def test_adjust_intra_day_move_applies_and_swaps_draft() -> None:
    service, env, _clock = make_service()
    proposed = service.propose(USER_ID)

    result = service.adjust(USER_ID, [_move("dp_001", datetime(2026, 5, 4, 16, 0, tzinfo=UTC))])

    assert result.applied is True
    assert result.reason_code is None
    assert result.state is S.AWAITING_USER_APPROVAL  # no lifecycle transition
    assert result.adjusted_task_ids == ["dp_001"]
    assert result.scheduled_task_count == 2
    # A new immutable draft replaced the pending one, with a fresh hash.
    assert result.draft_schedule_id != proposed.draft_schedule_id
    assert result.draft_payload_hash != proposed.draft_payload_hash
    # The run now points at the adjusted draft, and the move is persisted.
    run = env.state.latest_run_for_user(USER_ID)
    assert run is not None and run.draft_schedule_id == result.draft_schedule_id
    draft = env.state.get_draft(result.draft_schedule_id)
    assert draft is not None
    moved = next(e for e in draft.entries if e.task_id == "dp_001")
    assert moved.start == datetime(2026, 5, 4, 16, 0, tzinfo=UTC)
    assert moved.end == datetime(2026, 5, 4, 17, 0, tzinfo=UTC)  # 60m preserved


def test_adjust_cross_day_move_applies() -> None:
    service, env, _clock = make_service()
    service.propose(USER_ID)

    # dp_002 starts Wed; move it to Thursday morning.
    result = service.adjust(USER_ID, [_move("dp_002", datetime(2026, 5, 7, 10, 0, tzinfo=UTC))])

    assert result.applied is True
    draft = env.state.get_draft(result.draft_schedule_id)
    assert draft is not None
    moved = next(e for e in draft.entries if e.task_id == "dp_002")
    assert moved.start.date() == datetime(2026, 5, 7).date()  # Wed -> Thu
    assert (moved.end - moved.start).total_seconds() == 90 * 60  # duration preserved


def test_adjust_rejection_persists_nothing() -> None:
    service, env, _clock = make_service()
    proposed = service.propose(USER_ID)

    # Move dp_001 onto a fixed external event (server fetches/validates busy).
    busy = [{"start": "2026-05-04T16:30:00+00:00", "end": "2026-05-04T17:30:00+00:00"}]
    result = service.adjust(
        USER_ID,
        [_move("dp_001", datetime(2026, 5, 4, 16, 0, tzinfo=UTC))],
        free_busy=busy,
    )

    assert result.applied is False
    assert result.reason_code is ReasonCode.NO_VALID_CONTIGUOUS_BLOCK
    assert any(v.task_id == "dp_001" for v in result.violations)
    # Nothing persisted: the run still points at the original draft.
    run = env.state.latest_run_for_user(USER_ID)
    assert run is not None and run.draft_schedule_id == proposed.draft_schedule_id


def test_adjust_outside_hours_rejected() -> None:
    service, _env, _clock = make_service()
    service.propose(USER_ID)

    result = service.adjust(USER_ID, [_move("dp_001", datetime(2026, 5, 4, 7, 0, tzinfo=UTC))])

    assert result.applied is False
    assert result.reason_code is ReasonCode.OUTSIDE_ALLOWED_HOURS


def test_adjust_then_approve_uses_adjusted_draft() -> None:
    service, _env, _clock = make_service()
    proposed = service.propose(USER_ID)

    adjusted = service.adjust(USER_ID, [_move("dp_001", datetime(2026, 5, 4, 16, 0, tzinfo=UTC))])
    assert adjusted.applied is True

    approved = service.approve(USER_ID)
    # The approval locks the ADJUSTED draft's hash, not the original's, so the
    # axiom-06 write-time recheck validates exactly what the user approved.
    assert approved.approved_payload_hash == adjusted.draft_payload_hash
    assert approved.approved_payload_hash != proposed.draft_payload_hash


def test_adjust_after_approval_refused() -> None:
    service, _env, _clock = make_service()
    service.propose(USER_ID)
    service.approve(USER_ID)

    with pytest.raises(CycleError, match="awaiting_user_approval"):
        service.adjust(USER_ID, [_move("dp_001", datetime(2026, 5, 4, 16, 0, tzinfo=UTC))])


def test_adjust_unknown_task_id_refused() -> None:
    service, _env, _clock = make_service()
    service.propose(USER_ID)

    with pytest.raises(CycleError, match="unknown task_id"):
        service.adjust(USER_ID, [_move("nope", datetime(2026, 5, 4, 16, 0, tzinfo=UTC))])


def test_adjust_duplicate_task_id_refused() -> None:
    service, _env, _clock = make_service()
    service.propose(USER_ID)

    with pytest.raises(CycleError, match="duplicate task_id"):
        service.adjust(
            USER_ID,
            [
                _move("dp_001", datetime(2026, 5, 4, 16, 0, tzinfo=UTC)),
                _move("dp_001", datetime(2026, 5, 4, 17, 0, tzinfo=UTC)),
            ],
        )


def test_adjust_empty_refused() -> None:
    service, _env, _clock = make_service()
    service.propose(USER_ID)

    with pytest.raises(CycleError, match="no adjustments"):
        service.adjust(USER_ID, [])


def test_adjust_before_propose_refused() -> None:
    service, _env, _clock = make_service()
    # No run exists yet.
    with pytest.raises(CycleError, match="no run found"):
        service.adjust(USER_ID, [_move("dp_001", datetime(2026, 5, 4, 16, 0, tzinfo=UTC))])


def test_adjust_records_one_revealed_observation_per_adjusted_task() -> None:
    """An applied drag journals a DRAG_ADJUST observation per moved task,
    with the band of the new local start and the category from the plan
    (axiom 05 "Revealed-preference term")."""
    service, env, clock = make_service()
    service.propose(USER_ID)

    result = service.adjust(
        USER_ID,
        [
            _move("dp_001", datetime(2026, 5, 4, 16, 0, tzinfo=UTC)),
            _move("dp_002", datetime(2026, 5, 6, 18, 0, tzinfo=UTC)),
        ],
    )

    assert result.applied is True
    observations = env.placement_preference_store.list_for_user(USER_ID)
    assert [
        (o.task_id, o.category, o.time_of_day_band, o.source) for o in observations
    ] == [
        (
            "dp_001",
            TaskCategory.CONCEPT_REVIEW,
            TimeOfDayBand.AFTERNOON,
            PlacementPreferenceSource.DRAG_ADJUST,
        ),
        (
            "dp_002",
            TaskCategory.PRACTICE,
            TimeOfDayBand.EVENING,
            PlacementPreferenceSource.DRAG_ADJUST,
        ),
    ]
    assert all(o.observed_at == clock.now() for o in observations)


def test_adjust_rejected_move_records_no_observation() -> None:
    """A refused drag persists nothing — including no revealed preference."""
    service, env, _clock = make_service()
    service.propose(USER_ID)

    result = service.adjust(
        USER_ID, [_move("dp_001", datetime(2026, 5, 4, 7, 0, tzinfo=UTC))]
    )

    assert result.applied is False
    assert env.placement_preference_store.list_for_user(USER_ID) == []
