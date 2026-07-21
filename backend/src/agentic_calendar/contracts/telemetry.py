"""``telemetry`` contract.

Canonical spec: ``docs/specs/telemetry.schema.md`` (axiom 07, axiom 19).

:class:`TelemetryEvent` is the minimum privacy-first record of how one scheduled
task actually executed: scheduled vs actual duration, completion, reschedule
count, and data-quality tagging. It is the input to the drift classifier,
duration calibration, and metrics.

Two rules are enforced *here*:

1. **Privacy.** ``extra="forbid"`` structurally rejects raw calendar content
   (``calendar_event_title`` and friends). The MVP stores derived metadata
   only (telemetry spec "Privacy Rules"); a raw title in a payload is a schema
   error, not a stored field.
2. **Completion invariants.** A completed event must carry ``actual_duration_min``
   and ``completion_timestamp``. The *defaulting* that fills those in when a
   user omits them (→ ``duration_estimated`` + ``data_quality``) lives in the
   ingestion layer (``telemetry/ingestion.py``); by the time an event is a
   validated :class:`TelemetryEvent` the values are present.

``telemetry_event_id`` uniqueness / dedup is a store concern
(``telemetry/event_store.py``), not a single-object invariant.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DataQuality(StrEnum):
    """How trustworthy an event's values are (telemetry spec "Allowed Values").

    The calibration engine weights these differently: ``COMPLETE`` counts
    fully, ``MANUAL_BACKFILL`` at 0.5 weight; the drift classifier may exclude
    ``PARTIAL_ESTIMATED`` when sample size is otherwise sufficient.
    """

    COMPLETE = "complete"
    PARTIAL_ESTIMATED = "partial_estimated"
    OFFLINE_SYNCED = "offline_synced"
    MANUAL_BACKFILL = "manual_backfill"


class SolveConfidence(StrEnum):
    """The user's one-tap self-report of whether they own the material now.

    A distinct axis from ``subjective_difficulty`` (how hard it *felt* vs.
    whether the user could *do it again unaided*). Opt-in: skipping the triage
    is always allowed and never a penalty (empty-over-fabrication). The user
    reports it; code records it; an LLM never assigns it (axiom 08
    source-confidence rule). It feeds the mastery basis fold
    (``08-mastery-memory.md``); the confidence weighting itself lands in MM-B.
    """

    CONFIDENT = "confident"
    UNSURE = "unsure"
    NEEDED_HELP = "needed_help"


class TelemetryEvent(BaseModel):
    """One append-only record of a task's execution outcome."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    telemetry_event_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    scheduled_duration_min: int = Field(gt=0)
    actual_duration_min: int | None = Field(default=None, gt=0)
    completed: bool
    completion_timestamp: datetime | None = None
    user_reschedule_count: int = Field(ge=0)
    data_quality: DataQuality
    subjective_difficulty: int | None = Field(default=None, ge=1, le=5)
    solve_confidence: SolveConfidence | None = None
    duration_estimated: bool = False
    captured_offline: bool = False
    synced_at: datetime | None = None

    @model_validator(mode="after")
    def _completed_requires_actuals(self) -> TelemetryEvent:
        """A completed event must have actual duration and completion time.

        The ingestion layer defaults these (and flips ``duration_estimated`` /
        ``data_quality``) before constructing the model, so a *validated* event
        always has them. A completed payload still missing ``actual_duration_min``
        is the telemetry-spec invalid example and is rejected here.
        """
        if self.completed:
            if self.actual_duration_min is None:
                raise ValueError(
                    "completed event requires actual_duration_min "
                    "(ingestion defaults it with duration_estimated=true)"
                )
            if self.completion_timestamp is None:
                raise ValueError(
                    "completed event requires completion_timestamp "
                    "(ingestion defaults it from the scheduled end time)"
                )
        return self

    @model_validator(mode="after")
    def _confidence_requires_completion(self) -> TelemetryEvent:
        """A solve-confidence self-report only makes sense on a completed task.

        Telemetry-spec invariant (``08-mastery-memory.md``): ``solve_confidence``
        present implies ``completed: true``. A confidence report on an
        uncompleted task is contradictory and rejected (the spec invalid
        example). Absence is always allowed - the signal is opt-in.
        """
        if self.solve_confidence is not None and not self.completed:
            raise ValueError(
                "solve_confidence requires completed=true "
                "(a confidence self-report on an uncompleted task is contradictory)"
            )
        return self

    @model_validator(mode="after")
    def _offline_not_complete_quality(self) -> TelemetryEvent:
        """Offline-captured events can never claim fully-trusted ``complete``.

        Telemetry spec invariant: ``captured_offline: true`` must carry
        ``offline_synced`` (or a stricter value if backfilled), and the offline
        handling section permits ``partial_estimated`` when values were also
        defaulted. The one thing it can never be is ``complete`` ("all fields
        user-provided"), which is the spec's invalid example.
        """
        if self.captured_offline and self.data_quality is DataQuality.COMPLETE:
            raise ValueError(
                "captured_offline event cannot have data_quality 'complete'; "
                "use 'offline_synced' (or stricter)"
            )
        return self

    @model_validator(mode="after")
    def _estimated_not_complete_quality(self) -> TelemetryEvent:
        """A system-estimated duration is incompatible with ``complete``.

        ``duration_estimated: true`` means the system filled in
        ``actual_duration_min``; ``complete`` means every field was
        user-provided. The two cannot both hold.
        """
        if self.duration_estimated and self.data_quality is DataQuality.COMPLETE:
            raise ValueError(
                "duration_estimated=true is incompatible with data_quality "
                "'complete'; use 'partial_estimated'"
            )
        return self

    @model_validator(mode="after")
    def _timestamps_aware(self) -> TelemetryEvent:
        for label, value in (
            ("completion_timestamp", self.completion_timestamp),
            ("synced_at", self.synced_at),
        ):
            if value is not None and value.tzinfo is None:
                raise ValueError(f"{label} must be timezone-aware")
        return self
