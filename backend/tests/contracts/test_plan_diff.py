"""Tests for the ``PlanDiff`` contract (Phase 2)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from agentic_calendar.contracts.plan_diff import (
    DiffChangeType,
    FieldChange,
    PlanDiff,
    PlanDiffSummary,
    TaskChange,
)
from agentic_calendar.contracts.reason_codes import ReasonCode


def _summary(**overrides: object) -> PlanDiffSummary:
    base: dict[str, object] = {
        "tasks_added": 1,
        "tasks_removed": 0,
        "tasks_rescheduled": 0,
        "tasks_with_duration_changes": 0,
        "modules_affected": ("dp",),
        "net_weekly_load_change_min": 60,
        "timeline_change_days": 0,
    }
    base.update(overrides)
    return PlanDiffSummary(**base)  # type: ignore[arg-type]


def _diff(
    task_changes: tuple[TaskChange, ...] | None = None,
    field_changes: tuple[FieldChange, ...] = (),
    summary: PlanDiffSummary | None = None,
    **overrides: object,
) -> PlanDiff:
    base: dict[str, object] = {
        "diff_id": "diff_001",
        "from_plan_version": "plan_a",
        "to_plan_version": "plan_b",
        "computed_at": datetime(2026, 5, 7, 18, 0, tzinfo=UTC),
        "summary": summary or _summary(),
        "task_changes": task_changes
        or (
            TaskChange(
                task_id="dp_007",
                change_type=DiffChangeType.ADDED,
                user_facing_summary="Added: x",
            ),
        ),
        "field_changes": field_changes,
    }
    base.update(overrides)
    return PlanDiff(**base)  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# Summary / TaskChange / FieldChange
# --------------------------------------------------------------------------- #


def test_summary_round_trip() -> None:
    s = _summary()
    again = PlanDiffSummary.model_validate(s.model_dump(mode="json"))
    assert again == s


def test_summary_negative_count_rejected() -> None:
    with pytest.raises(ValidationError):
        _summary(tasks_added=-1)


def test_task_change_round_trip() -> None:
    tc = TaskChange(
        task_id="x",
        change_type=DiffChangeType.RESCHEDULED,
        user_facing_summary="Moved from Mon to Tue",
    )
    again = TaskChange.model_validate(tc.model_dump(mode="json"))
    assert again == tc


def test_field_change_round_trip() -> None:
    fc = FieldChange(
        task_id="x",
        field="scheduled_start",
        old_value="2026-05-05T19:00:00-07:00",
        new_value="2026-05-07T20:00:00-07:00",
        delta_minutes=2820,
        reason_code=ReasonCode.DEEP_WORK_WINDOW_CONFLICT,
    )
    again = FieldChange.model_validate(fc.model_dump(mode="json"))
    assert again == fc


def test_field_change_rejects_non_diff_reason_code() -> None:
    with pytest.raises(ValidationError, match="not in the"):
        FieldChange(
            task_id="x",
            field="f",
            reason_code=ReasonCode.APPROVAL_MISSING,
        )


@pytest.mark.parametrize(
    "rc",
    [
        ReasonCode.DEEP_WORK_WINDOW_CONFLICT,
        ReasonCode.USER_DURATION_CALIBRATION,
        ReasonCode.DEPENDENCY_RESCHEDULED,
        ReasonCode.WEEKLY_CAPACITY_REBALANCE,
        ReasonCode.EXTERNAL_CALENDAR_CONFLICT,
        ReasonCode.USER_PROFILE_CHANGE,
        ReasonCode.DRIFT_REMEDIATION,
        ReasonCode.DEPENDENT_DROP_PRUNED,
    ],
)
def test_field_change_accepts_each_allowed_reason_code(rc: ReasonCode) -> None:
    fc = FieldChange(task_id="x", field="f", reason_code=rc)
    assert fc.reason_code is rc


# --------------------------------------------------------------------------- #
# PlanDiff invariants
# --------------------------------------------------------------------------- #


def test_diff_round_trip() -> None:
    d = _diff()
    again = PlanDiff.model_validate(d.model_dump(mode="json"))
    assert again == d


def test_naive_computed_at_rejected() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        _diff(computed_at=datetime(2026, 5, 7, 18, 0))


def test_same_from_to_rejected() -> None:
    with pytest.raises(ValidationError, match="must differ"):
        _diff(from_plan_version="plan_x", to_plan_version="plan_x")


def test_no_task_added_and_removed() -> None:
    tcs = (
        TaskChange(task_id="t1", change_type=DiffChangeType.ADDED, user_facing_summary="Added"),
        TaskChange(task_id="t1", change_type=DiffChangeType.REMOVED, user_facing_summary="Removed"),
    )
    with pytest.raises(ValidationError, match="both added and removed"):
        _diff(task_changes=tcs)


def test_field_change_referencing_unknown_task_rejected() -> None:
    tcs = (
        TaskChange(task_id="t1", change_type=DiffChangeType.ADDED, user_facing_summary="ok"),
    )
    fcs = (
        FieldChange(
            task_id="missing",
            field="scheduled_start",
            reason_code=ReasonCode.DEEP_WORK_WINDOW_CONFLICT,
        ),
    )
    with pytest.raises(ValidationError, match="no matching"):
        _diff(task_changes=tcs, field_changes=fcs)


def test_field_change_referencing_known_task_accepted() -> None:
    tcs = (
        TaskChange(
            task_id="t1",
            change_type=DiffChangeType.RESCHEDULED,
            user_facing_summary="moved",
        ),
    )
    fcs = (
        FieldChange(
            task_id="t1",
            field="scheduled_start",
            reason_code=ReasonCode.DEEP_WORK_WINDOW_CONFLICT,
        ),
    )
    d = _diff(task_changes=tcs, field_changes=fcs)
    assert len(d.field_changes) == 1


def test_modules_affected_must_be_unique() -> None:
    with pytest.raises(ValidationError, match="unique values"):
        _diff(summary=_summary(modules_affected=("dp", "dp")))


def test_diff_extra_field_rejected() -> None:
    base = _diff()
    payload = base.model_dump(mode="json")
    payload["extra"] = "nope"
    with pytest.raises(ValidationError):
        PlanDiff.model_validate(payload)


def test_diff_is_frozen() -> None:
    d = _diff()
    with pytest.raises(ValidationError):
        d.diff_id = "other"  # type: ignore[misc]


@pytest.mark.parametrize("change_type", list(DiffChangeType))
def test_every_change_type_constructs(change_type: DiffChangeType) -> None:
    tc = TaskChange(task_id="t", change_type=change_type, user_facing_summary="x")
    assert tc.change_type is change_type
