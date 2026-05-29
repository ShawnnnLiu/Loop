"""Tests for the canonical payload hashing primitive (Phase 2)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from agentic_calendar.contracts.draft_schedule import (
    DraftSchedule,
    DraftScheduleEntry,
)
from agentic_calendar.contracts.hashing import (
    UnsupportedCanonicalizationVersionError,
    canonical_payload_hash,
    get_canonicalizer,
    register_canonicalizer,
    verify_payload_hash,
)
from agentic_calendar.contracts.reason_codes import ReasonCode
from agentic_calendar.contracts.scheduler_output import (
    RepairOption,
    ScheduledTask,
    SchedulerOutput,
    ScheduleStatus,
    UnscheduledTask,
)


def _entry(
    task_id: str = "t1",
    start: datetime = datetime(2026, 5, 4, 18, 0, tzinfo=UTC),
    end: datetime = datetime(2026, 5, 4, 19, 0, tzinfo=UTC),
) -> DraftScheduleEntry:
    return DraftScheduleEntry(task_id=task_id, start=start, end=end)


def _draft(entries: tuple[DraftScheduleEntry, ...] | None = None) -> DraftSchedule:
    return DraftSchedule(
        draft_schedule_id="draft_001",
        plan_version="plan_001",
        entries=entries if entries is not None else (_entry(),),
        created_at=datetime(2026, 5, 4, 17, 55, tzinfo=UTC),
    )


# --------------------------------------------------------------------------- #
# canonical_payload_hash
# --------------------------------------------------------------------------- #


def test_hash_has_sha256_prefix_and_64_hex_digits() -> None:
    h = canonical_payload_hash(_draft())
    prefix, _, digest = h.partition(":")
    assert prefix == "sha256"
    assert len(digest) == 64
    assert all(c in "0123456789abcdef" for c in digest)


def test_hash_is_stable_across_calls() -> None:
    h1 = canonical_payload_hash(_draft())
    h2 = canonical_payload_hash(_draft())
    assert h1 == h2


def test_hash_changes_when_entries_reordered() -> None:
    a = _entry(
        task_id="a",
        start=datetime(2026, 5, 4, 8, 0, tzinfo=UTC),
        end=datetime(2026, 5, 4, 9, 0, tzinfo=UTC),
    )
    b = _entry(
        task_id="b",
        start=datetime(2026, 5, 4, 18, 0, tzinfo=UTC),
        end=datetime(2026, 5, 4, 19, 0, tzinfo=UTC),
    )
    h_ab = canonical_payload_hash(_draft(entries=(a, b)))
    h_ba = canonical_payload_hash(_draft(entries=(b, a)))
    assert h_ab != h_ba


def test_hash_changes_when_task_id_changes() -> None:
    h1 = canonical_payload_hash(_draft(entries=(_entry(task_id="t1"),)))
    h2 = canonical_payload_hash(_draft(entries=(_entry(task_id="t2"),)))
    assert h1 != h2


def test_hash_changes_when_start_changes() -> None:
    h1 = canonical_payload_hash(_draft())
    h2 = canonical_payload_hash(
        _draft(
            entries=(
                _entry(
                    start=datetime(2026, 5, 4, 18, 1, tzinfo=UTC),
                ),
            )
        )
    )
    assert h1 != h2


def test_hash_changes_when_end_changes() -> None:
    h1 = canonical_payload_hash(_draft())
    h2 = canonical_payload_hash(
        _draft(
            entries=(
                _entry(
                    end=datetime(2026, 5, 4, 19, 30, tzinfo=UTC),
                ),
            )
        )
    )
    assert h1 != h2


def test_hash_changes_when_plan_version_changes() -> None:
    d1 = _draft()
    d2 = DraftSchedule(
        draft_schedule_id=d1.draft_schedule_id,
        plan_version="plan_DIFFERENT",
        entries=d1.entries,
        created_at=d1.created_at,
    )
    assert canonical_payload_hash(d1) != canonical_payload_hash(d2)


def test_hash_changes_when_draft_schedule_id_changes() -> None:
    d1 = _draft()
    d2 = DraftSchedule(
        draft_schedule_id="draft_DIFFERENT",
        plan_version=d1.plan_version,
        entries=d1.entries,
        created_at=d1.created_at,
    )
    assert canonical_payload_hash(d1) != canonical_payload_hash(d2)


def test_hash_unchanged_when_created_at_changes() -> None:
    """Axiom 06 line 161-163: server timestamps are NOT in the hashed payload."""
    d1 = _draft()
    d2 = DraftSchedule(
        draft_schedule_id=d1.draft_schedule_id,
        plan_version=d1.plan_version,
        entries=d1.entries,
        created_at=datetime(2026, 7, 4, 17, 55, tzinfo=UTC),  # different
    )
    assert canonical_payload_hash(d1) == canonical_payload_hash(d2)


def test_hash_unchanged_when_unrelated_scheduler_output_field_changes() -> None:
    """Two SchedulerOutputs that differ only in repair_options must produce
    the same DraftSchedule and therefore the same hash."""
    scheduled = [
        ScheduledTask(
            task_id="t1",
            start=datetime(2026, 5, 4, 18, 0, tzinfo=UTC),
            end=datetime(2026, 5, 4, 19, 0, tzinfo=UTC),
        )
    ]
    out_a = SchedulerOutput(
        run_id="r",
        plan_version="p",
        schedule_status=ScheduleStatus.PARTIAL_FAILURE,
        scheduled_tasks=scheduled,
        unscheduled_tasks=[
            UnscheduledTask(
                task_id="bad",
                reason_code=ReasonCode.NO_VALID_CONTIGUOUS_BLOCK,
                debug={"why": "x"},
            )
        ],
        available_capacity_min=120,
        largest_available_block_min=60,
        repair_options=[RepairOption.ASK_USER],
    )
    out_b = SchedulerOutput(
        run_id="r",
        plan_version="p",
        schedule_status=ScheduleStatus.PARTIAL_FAILURE,
        scheduled_tasks=scheduled,
        unscheduled_tasks=[
            UnscheduledTask(
                task_id="bad",
                reason_code=ReasonCode.NO_VALID_CONTIGUOUS_BLOCK,
                debug={"why": "x"},
            )
        ],
        available_capacity_min=999,  # different
        largest_available_block_min=999,  # different
        repair_options=[
            RepairOption.SPLIT_LARGE_TASKS,
            RepairOption.EXTEND_TIMELINE,
        ],  # different
    )
    da = DraftSchedule.from_scheduler_output(
        out_a, draft_schedule_id="d", created_at=datetime(2026, 5, 4, tzinfo=UTC)
    )
    db = DraftSchedule.from_scheduler_output(
        out_b, draft_schedule_id="d", created_at=datetime(2026, 5, 4, tzinfo=UTC)
    )
    assert canonical_payload_hash(da) == canonical_payload_hash(db)


# --------------------------------------------------------------------------- #
# verify_payload_hash
# --------------------------------------------------------------------------- #


def test_verify_returns_true_for_matching_hash() -> None:
    draft = _draft()
    h = canonical_payload_hash(draft)
    assert verify_payload_hash(draft, h, "v1") is True


def test_verify_returns_false_for_mismatched_hash() -> None:
    draft = _draft()
    h = canonical_payload_hash(draft)
    bad = h[:-1] + ("0" if h[-1] != "0" else "1")
    assert verify_payload_hash(draft, bad, "v1") is False


# --------------------------------------------------------------------------- #
# Canonicalizer registry
# --------------------------------------------------------------------------- #


def test_unknown_version_raises_on_hash() -> None:
    with pytest.raises(UnsupportedCanonicalizationVersionError):
        canonical_payload_hash(_draft(), version="vDOES_NOT_EXIST")


def test_unknown_version_raises_on_get() -> None:
    with pytest.raises(UnsupportedCanonicalizationVersionError):
        get_canonicalizer("vDOES_NOT_EXIST")


def test_register_then_get_round_trip() -> None:
    def custom(draft: DraftSchedule) -> bytes:
        return b"const"

    register_canonicalizer("test_register_then_get_round_trip", custom)
    got = get_canonicalizer("test_register_then_get_round_trip")
    assert got is custom


def test_register_twice_with_same_fn_is_idempotent() -> None:
    def custom(draft: DraftSchedule) -> bytes:
        return b"const"

    register_canonicalizer("test_register_twice_idempotent", custom)
    register_canonicalizer("test_register_twice_idempotent", custom)


def test_register_conflicting_version_raises() -> None:
    def first(draft: DraftSchedule) -> bytes:
        return b"a"

    def second(draft: DraftSchedule) -> bytes:
        return b"b"

    register_canonicalizer("test_register_conflicting", first)
    with pytest.raises(ValueError, match="already registered"):
        register_canonicalizer("test_register_conflicting", second)


def test_empty_version_rejected_on_register() -> None:
    def fn(draft: DraftSchedule) -> bytes:
        return b""

    with pytest.raises(ValueError, match="non-empty"):
        register_canonicalizer("", fn)


def test_custom_version_round_trips_through_hash() -> None:
    def constant(draft: DraftSchedule) -> bytes:
        return b"CONSTANT_PAYLOAD"

    register_canonicalizer("test_custom_version_round_trips", constant)
    h1 = canonical_payload_hash(_draft(), version="test_custom_version_round_trips")
    h2 = canonical_payload_hash(
        _draft(entries=(_entry(task_id="DIFFERENT"),)),
        version="test_custom_version_round_trips",
    )
    # Both inputs produce the same hash because the canonicalizer ignores the
    # draft contents.
    assert h1 == h2
