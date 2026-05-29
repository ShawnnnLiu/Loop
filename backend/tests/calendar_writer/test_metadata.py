"""Tests for ``calendar_writer/metadata.py`` (Phase 2)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from agentic_calendar.calendar_writer.adapter import ExternalEventRecord
from agentic_calendar.calendar_writer.metadata import (
    APP_TAG,
    build_event_metadata,
    verify_event_metadata,
)


def _record(metadata: dict[str, str]) -> ExternalEventRecord:
    return ExternalEventRecord(
        calendar_event_id="gcal_evt_x",
        target_calendar_id="primary",
        scheduled_start=datetime(2026, 5, 4, 18, 0, tzinfo=UTC),
        scheduled_end=datetime(2026, 5, 4, 19, 0, tzinfo=UTC),
        metadata=metadata,
    )


def test_app_tag_is_career_scheduler() -> None:
    assert APP_TAG == "career_scheduler"


def test_build_metadata_has_required_keys() -> None:
    md = build_event_metadata(run_id="r", plan_version="p", task_id="t")
    assert md == {
        "app": "career_scheduler",
        "run_id": "r",
        "plan_version": "p",
        "task_id": "t",
    }


def test_build_rejects_empty_run_id() -> None:
    with pytest.raises(ValueError):
        build_event_metadata(run_id="", plan_version="p", task_id="t")


def test_build_rejects_empty_plan_version() -> None:
    with pytest.raises(ValueError):
        build_event_metadata(run_id="r", plan_version="", task_id="t")


def test_build_rejects_empty_task_id() -> None:
    with pytest.raises(ValueError):
        build_event_metadata(run_id="r", plan_version="p", task_id="")


# --------------------------------------------------------------------------- #
# verify_event_metadata
# --------------------------------------------------------------------------- #


def test_verify_returns_true_for_matching_metadata() -> None:
    record = _record({"app": APP_TAG, "run_id": "r", "plan_version": "p", "task_id": "t"})
    assert verify_event_metadata(record, run_id="r", plan_version="p", task_id="t")


def test_verify_returns_false_for_wrong_app_tag() -> None:
    record = _record({"app": "other", "run_id": "r", "plan_version": "p", "task_id": "t"})
    assert not verify_event_metadata(record, run_id="r", plan_version="p", task_id="t")


def test_verify_returns_false_for_wrong_run_id() -> None:
    record = _record(
        {"app": APP_TAG, "run_id": "different", "plan_version": "p", "task_id": "t"}
    )
    assert not verify_event_metadata(record, run_id="r", plan_version="p", task_id="t")


def test_verify_returns_false_for_wrong_plan_version() -> None:
    record = _record(
        {"app": APP_TAG, "run_id": "r", "plan_version": "different", "task_id": "t"}
    )
    assert not verify_event_metadata(record, run_id="r", plan_version="p", task_id="t")


def test_verify_returns_false_for_wrong_task_id() -> None:
    record = _record(
        {"app": APP_TAG, "run_id": "r", "plan_version": "p", "task_id": "different"}
    )
    assert not verify_event_metadata(record, run_id="r", plan_version="p", task_id="t")


def test_verify_returns_false_for_missing_keys() -> None:
    record = _record({"app": APP_TAG, "run_id": "r"})
    assert not verify_event_metadata(record, run_id="r", plan_version="p", task_id="t")


def test_verify_tolerates_extra_keys() -> None:
    record = _record(
        {
            "app": APP_TAG,
            "run_id": "r",
            "plan_version": "p",
            "task_id": "t",
            "extra": "value",
        }
    )
    assert verify_event_metadata(record, run_id="r", plan_version="p", task_id="t")
