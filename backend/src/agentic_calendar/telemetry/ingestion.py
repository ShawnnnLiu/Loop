"""Telemetry ingestion (Phase 4).

Turns a raw client/API payload into a validated, stored :class:`TelemetryEvent`,
deterministically. Three jobs:

1. **Defaulting** (telemetry-spec invariants): a completed event missing
   ``actual_duration_min`` defaults it to ``scheduled_duration_min`` with
   ``duration_estimated=True``; a completed event missing ``completion_timestamp``
   defaults it to the scheduled end (when known) or the sync time. Either
   default downgrades ``data_quality`` away from ``complete``.
2. **Privacy guard**: an explicit denylist rejects raw calendar content with a
   clear, auditable message (telemetry-spec "Privacy Rules"); the contract's
   ``extra="forbid"`` is the structural backstop for anything the denylist
   misses.
3. **Dedup + append**: reingesting the same ``telemetry_event_id`` is idempotent
   (returns ``DUPLICATE``), never an error and never a second row.

Every outcome is typed — no raw exception crosses this boundary (axiom 16).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import ValidationError

from agentic_calendar.common.clock import Clock
from agentic_calendar.contracts.reason_codes import ReasonCode
from agentic_calendar.contracts.telemetry import DataQuality, TelemetryEvent

from .event_store import TelemetryEventStore

#: Keys that must never reach telemetry storage (telemetry-spec "Privacy Rules").
#: ``extra="forbid"`` on the contract already blocks unknown keys; this explicit
#: list exists so a privacy violation gets a named, auditable rejection rather
#: than a generic "extra fields" error.
_PRIVACY_DENYLIST: frozenset[str] = frozenset(
    {
        "calendar_event_title",
        "calendar_event_description",
        "event_title",
        "event_description",
        "notes",
        "user_notes",
        "raw_calendar_metadata",
    }
)


class IngestionStatus(StrEnum):
    """Outcome of one ingestion attempt."""

    INGESTED = "ingested"
    DUPLICATE = "duplicate"
    REJECTED = "rejected"


@dataclass(frozen=True)
class IngestionOutcome:
    """Result of :meth:`TelemetryIngestor.ingest`.

    ``event`` is the stored event on ``INGESTED``, the pre-existing event on
    ``DUPLICATE``, and ``None`` on ``REJECTED``. ``reason_code`` is set only on
    ``REJECTED``.
    """

    status: IngestionStatus
    event: TelemetryEvent | None
    reason_code: ReasonCode | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.status is IngestionStatus.INGESTED


class TelemetryIngestor:
    """Deterministically validate, default, dedup, and store telemetry events."""

    def __init__(self, *, clock: Clock, store: TelemetryEventStore) -> None:
        self._clock = clock
        self._store = store

    def ingest(
        self,
        payload: Mapping[str, Any],
        *,
        scheduled_end: datetime | None = None,
    ) -> IngestionOutcome:
        """Ingest one raw telemetry payload.

        ``scheduled_end`` is the task's scheduled end time, used to default a
        missing ``completion_timestamp`` (telemetry-spec invariant). When the
        caller does not know it, the sync time (``clock.now()``) is used and the
        event is tagged as estimated.
        """
        privacy_hit = _PRIVACY_DENYLIST.intersection(payload.keys())
        if privacy_hit:
            offending = sorted(privacy_hit)
            return IngestionOutcome(
                status=IngestionStatus.REJECTED,
                event=None,
                reason_code=ReasonCode.SCHEMA_INVALID,
                error=(
                    "privacy: raw calendar fields are not storable "
                    f"(telemetry spec Privacy Rules): {offending}"
                ),
            )

        prepared = self._apply_defaults(dict(payload), scheduled_end=scheduled_end)

        try:
            event = TelemetryEvent.model_validate(prepared)
        except ValidationError as exc:
            return IngestionOutcome(
                status=IngestionStatus.REJECTED,
                event=None,
                reason_code=ReasonCode.SCHEMA_INVALID,
                error=str(exc),
            )

        existing = self._store.get(event.telemetry_event_id)
        if existing is not None:
            return IngestionOutcome(status=IngestionStatus.DUPLICATE, event=existing)

        self._store.append(event)
        return IngestionOutcome(status=IngestionStatus.INGESTED, event=event)

    def _apply_defaults(
        self,
        data: dict[str, Any],
        *,
        scheduled_end: datetime | None,
    ) -> dict[str, Any]:
        """Apply the telemetry-spec completion defaults, in place, to ``data``.

        Pure aside from reading ``self._clock`` for the sync-time fallback.
        """
        estimated = False

        if data.get("completed"):
            if data.get("actual_duration_min") is None:
                scheduled = data.get("scheduled_duration_min")
                if isinstance(scheduled, int) and scheduled > 0:
                    data["actual_duration_min"] = scheduled
                    data["duration_estimated"] = True
                    estimated = True
            if data.get("completion_timestamp") is None:
                data["completion_timestamp"] = (
                    scheduled_end if scheduled_end is not None else self._clock.now()
                )
                estimated = True

        # data_quality normalization: an offline or estimated event can never
        # remain fully-trusted ``complete``.
        quality = data.get("data_quality")
        if data.get("captured_offline") and quality == DataQuality.COMPLETE.value:
            data["data_quality"] = DataQuality.OFFLINE_SYNCED.value
        elif estimated and quality == DataQuality.COMPLETE.value:
            data["data_quality"] = DataQuality.PARTIAL_ESTIMATED.value

        return data
