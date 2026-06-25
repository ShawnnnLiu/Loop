"""Contract tests for :class:`TaskDispositionRecord` (task-disposition spec)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from agentic_calendar.contracts.reason_codes import ReasonCode
from agentic_calendar.contracts.task_disposition import (
    DispositionSource,
    TaskDispositionRecord,
    TaskDispositionType,
)

_NOW = datetime(2026, 6, 24, 19, 0, tzinfo=UTC)


def _record(
    *,
    disposition: TaskDispositionType = TaskDispositionType.COMPLETED,
    reason_code: ReasonCode | None = None,
    source: DispositionSource = DispositionSource.SYSTEM,
    created_at: datetime = _NOW,
) -> TaskDispositionRecord:
    return TaskDispositionRecord(
        disposition_id="disp_1",
        user_id="user_1",
        plan_version="plan_1",
        task_id="dp_002",
        disposition=disposition,
        reason_code=reason_code,
        source=source,
        created_at=created_at,
    )


def test_completed_record_round_trips() -> None:
    record = _record()
    reloaded = TaskDispositionRecord.model_validate_json(record.model_dump_json())
    assert reloaded == record
    assert reloaded.disposition is TaskDispositionType.COMPLETED
    assert reloaded.reason_code is None


def test_dropped_record_round_trips() -> None:
    record = _record(
        disposition=TaskDispositionType.DROPPED,
        reason_code=ReasonCode.TASK_DROPPED_BY_USER,
        source=DispositionSource.USER,
    )
    reloaded = TaskDispositionRecord.model_validate_json(record.model_dump_json())
    assert reloaded == record
    assert reloaded.reason_code is ReasonCode.TASK_DROPPED_BY_USER


def test_dropped_requires_reason_code() -> None:
    with pytest.raises(ValidationError, match="dropped disposition must carry"):
        _record(disposition=TaskDispositionType.DROPPED, reason_code=None)


def test_completed_forbids_reason_code() -> None:
    with pytest.raises(ValidationError, match="completed disposition must have a null"):
        _record(
            disposition=TaskDispositionType.COMPLETED,
            reason_code=ReasonCode.TASK_DROPPED_BY_USER,
        )


def test_skipped_allows_either_reason_code() -> None:
    assert _record(disposition=TaskDispositionType.SKIPPED).reason_code is None
    with_code = _record(
        disposition=TaskDispositionType.SKIPPED,
        reason_code=ReasonCode.DEPENDENCY_ADVISORY,
    )
    assert with_code.reason_code is ReasonCode.DEPENDENCY_ADVISORY


def test_created_at_must_be_timezone_aware() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        _record(created_at=datetime(2026, 6, 24, 19, 0))


def test_unknown_field_rejected() -> None:
    payload = _record().model_dump(mode="json")
    payload["bogus"] = 1
    with pytest.raises(ValidationError):
        TaskDispositionRecord.model_validate(payload)
