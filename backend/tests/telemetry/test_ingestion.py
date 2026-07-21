"""Tests for deterministic telemetry ingestion (Phase 4)."""

from __future__ import annotations

from datetime import UTC, datetime

from agentic_calendar.common.clock import FrozenClock
from agentic_calendar.contracts.reason_codes import ReasonCode
from agentic_calendar.contracts.telemetry import DataQuality, SolveConfidence
from agentic_calendar.telemetry.event_store import InMemoryTelemetryEventStore
from agentic_calendar.telemetry.ingestion import (
    IngestionStatus,
    TelemetryIngestor,
)

NOW = datetime(2026, 5, 6, 20, 43, tzinfo=UTC)


def _ingestor() -> tuple[TelemetryIngestor, InMemoryTelemetryEventStore]:
    store = InMemoryTelemetryEventStore()
    return TelemetryIngestor(clock=FrozenClock(NOW), store=store), store


def test_completed_missing_actual_is_defaulted_and_downgraded() -> None:
    ing, _ = _ingestor()
    out = ing.ingest(
        {
            "telemetry_event_id": "tel_1",
            "task_id": "dp_2",
            "scheduled_duration_min": 90,
            "completed": True,
            "user_reschedule_count": 0,
            "data_quality": "complete",
        }
    )
    assert out.ok
    assert out.event is not None
    assert out.event.actual_duration_min == 90
    assert out.event.duration_estimated is True
    assert out.event.data_quality is DataQuality.PARTIAL_ESTIMATED
    # missing completion_timestamp defaulted to the sync time (clock.now())
    assert out.event.completion_timestamp == NOW


def test_completion_timestamp_defaults_to_scheduled_end_when_given() -> None:
    ing, _ = _ingestor()
    scheduled_end = datetime(2026, 5, 6, 18, 30, tzinfo=UTC)
    out = ing.ingest(
        {
            "telemetry_event_id": "tel_1",
            "task_id": "dp_2",
            "scheduled_duration_min": 45,
            "completed": True,
            "user_reschedule_count": 0,
            "data_quality": "complete",
        },
        scheduled_end=scheduled_end,
    )
    assert out.ok
    assert out.event is not None
    assert out.event.completion_timestamp == scheduled_end


def test_solve_confidence_passes_through_to_the_stored_event() -> None:
    ing, _ = _ingestor()
    out = ing.ingest(
        {
            "telemetry_event_id": "tel_1",
            "task_id": "dp_2",
            "scheduled_duration_min": 45,
            "actual_duration_min": 45,
            "completed": True,
            "completion_timestamp": NOW.isoformat(),
            "user_reschedule_count": 0,
            "data_quality": "complete",
            "solve_confidence": "needed_help",
        }
    )
    assert out.ok
    assert out.event is not None
    assert out.event.solve_confidence is SolveConfidence.NEEDED_HELP


def test_solve_confidence_on_incomplete_is_rejected() -> None:
    # The contract invariant (present ⟹ completed) is the backstop even if a
    # caller bypasses the service-layer guard.
    ing, _ = _ingestor()
    out = ing.ingest(
        {
            "telemetry_event_id": "tel_1",
            "task_id": "dp_2",
            "scheduled_duration_min": 45,
            "completed": False,
            "user_reschedule_count": 0,
            "data_quality": "complete",
            "solve_confidence": "confident",
        }
    )
    assert out.status is IngestionStatus.REJECTED
    assert out.reason_code is ReasonCode.SCHEMA_INVALID


def test_reingestion_is_idempotent_duplicate() -> None:
    ing, store = _ingestor()
    payload = {
        "telemetry_event_id": "tel_1",
        "task_id": "dp_2",
        "scheduled_duration_min": 90,
        "actual_duration_min": 100,
        "completed": True,
        "completion_timestamp": "2026-05-06T19:00:00+00:00",
        "user_reschedule_count": 0,
        "data_quality": "complete",
    }
    first = ing.ingest(payload)
    second = ing.ingest({**payload, "actual_duration_min": 999})
    assert first.status is IngestionStatus.INGESTED
    assert second.status is IngestionStatus.DUPLICATE
    # the stored event is the original, not the retried payload
    assert second.event is not None
    assert second.event.actual_duration_min == 100
    assert len(store.all()) == 1


def test_privacy_denylist_rejects_raw_calendar_title() -> None:
    ing, store = _ingestor()
    out = ing.ingest(
        {
            "telemetry_event_id": "tel_1",
            "task_id": "dp_2",
            "scheduled_duration_min": 90,
            "completed": False,
            "user_reschedule_count": 0,
            "data_quality": "complete",
            "calendar_event_title": "Solve memoization practice set",
        }
    )
    assert out.status is IngestionStatus.REJECTED
    assert out.reason_code is ReasonCode.SCHEMA_INVALID
    assert out.error is not None and "Privacy Rules" in out.error
    assert len(store.all()) == 0


def test_schema_invalid_payload_is_rejected() -> None:
    ing, _ = _ingestor()
    out = ing.ingest(
        {
            "telemetry_event_id": "tel_1",
            "task_id": "dp_2",
            "scheduled_duration_min": -30,
            "completed": False,
            "user_reschedule_count": 0,
            "data_quality": "complete",
        }
    )
    assert out.status is IngestionStatus.REJECTED
    assert out.reason_code is ReasonCode.SCHEMA_INVALID


def test_offline_complete_quality_is_normalized() -> None:
    ing, _ = _ingestor()
    out = ing.ingest(
        {
            "telemetry_event_id": "tel_1",
            "task_id": "dp_2",
            "scheduled_duration_min": 60,
            "actual_duration_min": 60,
            "completed": True,
            "completion_timestamp": "2026-05-06T19:00:00+00:00",
            "user_reschedule_count": 0,
            "data_quality": "complete",
            "captured_offline": True,
        }
    )
    assert out.ok
    assert out.event is not None
    assert out.event.data_quality is DataQuality.OFFLINE_SYNCED


def test_fully_specified_event_passes_through_unchanged() -> None:
    ing, _ = _ingestor()
    out = ing.ingest(
        {
            "telemetry_event_id": "tel_1",
            "task_id": "dp_2",
            "scheduled_duration_min": 90,
            "actual_duration_min": 135,
            "completed": True,
            "completion_timestamp": "2026-05-06T20:42:00+00:00",
            "user_reschedule_count": 2,
            "subjective_difficulty": 4,
            "data_quality": "complete",
        }
    )
    assert out.ok
    assert out.event is not None
    assert out.event.duration_estimated is False
    assert out.event.data_quality is DataQuality.COMPLETE
    assert out.event.subjective_difficulty == 4
