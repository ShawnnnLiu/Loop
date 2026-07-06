"""``calendar_reconciliation`` contract.

Canonical spec: ``docs/specs/calendar-reconciliation.schema.md`` (axiom 06).

Inbound reconciliation detects that the user directly edited the app's own
events on their dedicated external calendar (moved / resized / deleted) and
deterministically **adopts valid edits** into the internal schedule while
**flagging invalid edits and deletions** for the drift loop. This module owns
the result/delta shapes only; the deterministic service that produces them and
the adopt-if-valid policy live in the composition layer (it must read the
adapter and reuse the scheduler's placement validator, both sibling regions).

Framing invariants enforced here (the spec's "Invariants" section):

* An ``adopted`` delta carries a ``null`` ``reason_code``, or one advisory
  heads-up: ``DAILY_LOAD_ADVISORY`` when the adopted move pushed its day over
  the daily cap (ADR-0010), ``DEPENDENCY_ADVISORY`` when it now precedes an
  unfinished prerequisite (ADR-0008), or ``OVERLAP_ADVISORY`` when it now
  overlaps another block or a busy interval (ADR-0009) — and is only a
  ``moved`` or ``resized`` change.
* A ``rejected`` delta carries one of the drag-to-adjust **hard** placement
  codes (the same vocabulary a UI move is refused with), never an unrelated
  code; prerequisite ordering, overlap, and daily load are advisory for an
  external move and never reject.
* A ``deleted`` change is always ``flagged_deleted`` with the
  ``EXTERNAL_EVENT_DELETED`` code and ``null`` observed times (the event is
  gone); the MVP never silently re-creates or cancels it.
* ``adopted_draft_schedule_id`` is present iff the ``outcome`` adopted at least
  one move (``adopted`` / ``mixed``); the no-comparison outcomes
  (``sync_disabled`` / ``deferred``) carry no deltas.

All models are ``frozen=True`` and forbid unknown fields, like the other
immutable contracts in this package.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .reason_codes import ReasonCode


class CalendarEditType(StrEnum):
    """How the live external event differs from our recorded placement."""

    UNCHANGED = "unchanged"
    MOVED = "moved"
    """Start changed; duration preserved."""
    RESIZED = "resized"
    """Duration changed (an external edge-drag; the in-app adjust path forbids
    resize, an external resize does not)."""
    DELETED = "deleted"
    """The mapped event is gone from the calendar."""


class ReconciliationDisposition(StrEnum):
    """What the deterministic service did with a single delta."""

    UNCHANGED = "unchanged"
    ADOPTED = "adopted"
    REJECTED = "rejected"
    FLAGGED_DELETED = "flagged_deleted"


class ReconciliationOutcome(StrEnum):
    """Roll-up of one reconciliation pull."""

    SYNC_DISABLED = "sync_disabled"
    """Opt-in off; no comparison ran (axiom 06 lines 249-253)."""
    DEFERRED = "deferred"
    """A write was in progress / the lock was held; no comparison ran."""
    NO_CHANGE = "no_change"
    """Compared, nothing the user touched."""
    ADOPTED = "adopted"
    """Every detected edit validated and was adopted."""
    FLAGGED = "flagged"
    """Detected edits, none adopted (all rejected / deleted)."""
    MIXED = "mixed"
    """Some edits adopted, some flagged."""


#: A rejected reconciliation delta must carry one of the drag-to-adjust **hard**
#: placement codes (``scheduler/adjustment.py``) — a calendar move is refused for
#: the same reasons a UI move is, so the vocabulary is shared. Prerequisite
#: ordering is no longer here: it is advisory (``DEPENDENCY_ADVISORY``) and never
#: rejects an external move (ADR-0008). ``NO_VALID_CONTIGUOUS_BLOCK`` and
#: ``DAILY_LOAD_EXCEEDED`` stay in the vocabulary — they are still the in-app
#: drag refusals, and historical results carry them — but the reconcile
#: producer no longer emits either: overlap and daily load on an external move
#: are advisory too (``OVERLAP_ADVISORY`` ADR-0009, ``DAILY_LOAD_ADVISORY``
#: ADR-0010), leaving ``OUTSIDE_ALLOWED_HOURS`` as the only emitted rejection.
ADJUSTMENT_REASON_CODES: frozenset[ReasonCode] = frozenset(
    {
        ReasonCode.NO_VALID_CONTIGUOUS_BLOCK,
        ReasonCode.OUTSIDE_ALLOWED_HOURS,
        ReasonCode.DAILY_LOAD_EXCEEDED,
    }
)


class CalendarEventDelta(BaseModel):
    """One mapped task's recorded-vs-observed difference and its disposition."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    task_id: str = Field(min_length=1)
    calendar_event_id: str | None
    change_type: CalendarEditType
    recorded_start: datetime
    recorded_end: datetime
    observed_start: datetime | None
    observed_end: datetime | None
    disposition: ReconciliationDisposition
    reason_code: ReasonCode | None = None

    @model_validator(mode="after")
    def _recorded_tz_aware_ordered(self) -> CalendarEventDelta:
        if self.recorded_start.tzinfo is None or self.recorded_end.tzinfo is None:
            raise ValueError(
                "reconciliation delta recorded_start/recorded_end must be timezone-aware"
            )
        if self.recorded_end <= self.recorded_start:
            raise ValueError(
                "reconciliation delta recorded_end must be strictly after recorded_start"
            )
        return self

    @model_validator(mode="after")
    def _observed_matches_change_type(self) -> CalendarEventDelta:
        if self.change_type is CalendarEditType.DELETED:
            if self.observed_start is not None or self.observed_end is not None:
                raise ValueError(
                    "a deleted reconciliation delta must have null "
                    "observed_start/observed_end (the event is gone)"
                )
            return self
        # moved / resized / unchanged all describe a live event.
        if self.observed_start is None or self.observed_end is None:
            raise ValueError(
                "a moved/resized/unchanged reconciliation delta requires "
                "observed_start/observed_end"
            )
        if self.observed_start.tzinfo is None or self.observed_end.tzinfo is None:
            raise ValueError(
                "reconciliation delta observed_start/observed_end must be timezone-aware"
            )
        if self.observed_end <= self.observed_start:
            raise ValueError(
                "reconciliation delta observed_end must be strictly after observed_start"
            )
        return self

    @model_validator(mode="after")
    def _disposition_consistent(self) -> CalendarEventDelta:
        match self.disposition:
            case ReconciliationDisposition.UNCHANGED:
                if (
                    self.change_type is not CalendarEditType.UNCHANGED
                    or self.reason_code is not None
                ):
                    raise ValueError(
                        "an unchanged delta must have change_type 'unchanged' and "
                        "a null reason_code"
                    )
            case ReconciliationDisposition.ADOPTED:
                if self.reason_code not in (
                    None,
                    ReasonCode.DEPENDENCY_ADVISORY,
                    ReasonCode.OVERLAP_ADVISORY,
                    ReasonCode.DAILY_LOAD_ADVISORY,
                ):
                    raise ValueError(
                        "an adopted reconciliation delta may carry only a null "
                        "reason_code, DEPENDENCY_ADVISORY (ADR-0008), "
                        "OVERLAP_ADVISORY (ADR-0009), or DAILY_LOAD_ADVISORY "
                        "(ADR-0010)"
                    )
                if self.change_type not in (
                    CalendarEditType.MOVED,
                    CalendarEditType.RESIZED,
                ):
                    raise ValueError(
                        "an adopted delta must be a 'moved' or 'resized' change"
                    )
            case ReconciliationDisposition.REJECTED:
                if self.reason_code not in ADJUSTMENT_REASON_CODES:
                    allowed = ", ".join(sorted(c.value for c in ADJUSTMENT_REASON_CODES))
                    raise ValueError(
                        "a rejected reconciliation delta must carry a placement "
                        f"reason_code (one of: {allowed})"
                    )
            case ReconciliationDisposition.FLAGGED_DELETED:
                if self.change_type is not CalendarEditType.DELETED:
                    raise ValueError(
                        "disposition 'flagged_deleted' requires change_type 'deleted'"
                    )
                if self.reason_code is not ReasonCode.EXTERNAL_EVENT_DELETED:
                    raise ValueError(
                        "a flagged_deleted delta must carry reason_code "
                        "'EXTERNAL_EVENT_DELETED'"
                    )
        return self


class CalendarReconciliationResult(BaseModel):
    """Outcome of one on-demand reconciliation pull for an active run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str = Field(min_length=1)
    plan_version: str = Field(min_length=1)
    reconciled_at: datetime
    target_calendar_id: str = Field(min_length=1)
    outcome: ReconciliationOutcome
    adopted_draft_schedule_id: str | None = None
    deltas: tuple[CalendarEventDelta, ...] = ()

    @model_validator(mode="after")
    def _reconciled_at_aware(self) -> CalendarReconciliationResult:
        if self.reconciled_at.tzinfo is None:
            raise ValueError("reconciliation reconciled_at must be timezone-aware")
        return self

    @model_validator(mode="after")
    def _adopted_id_consistent(self) -> CalendarReconciliationResult:
        adopting = self.outcome in (
            ReconciliationOutcome.ADOPTED,
            ReconciliationOutcome.MIXED,
        )
        if adopting:
            if self.adopted_draft_schedule_id is None:
                raise ValueError(
                    f"outcome {self.outcome.value!r} requires a non-null "
                    "adopted_draft_schedule_id"
                )
            if not any(
                d.disposition is ReconciliationDisposition.ADOPTED for d in self.deltas
            ):
                raise ValueError(
                    f"outcome {self.outcome.value!r} requires at least one adopted delta"
                )
        elif self.adopted_draft_schedule_id is not None:
            raise ValueError(
                "adopted_draft_schedule_id is only allowed when outcome is "
                "'adopted' or 'mixed'"
            )
        return self

    @model_validator(mode="after")
    def _no_comparison_has_no_deltas(self) -> CalendarReconciliationResult:
        if (
            self.outcome
            in (ReconciliationOutcome.SYNC_DISABLED, ReconciliationOutcome.DEFERRED)
            and self.deltas
        ):
            raise ValueError(
                f"outcome {self.outcome.value!r} ran no comparison and must carry "
                "no deltas"
            )
        return self
