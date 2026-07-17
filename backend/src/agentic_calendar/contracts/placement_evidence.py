"""``placement_evidence`` contract.

Canonical spec: ``docs/specs/placement-evidence.schema.md``.

:class:`PlacementEvidence` carries per-user time-of-day evidence — where the
user historically works best, keyed by ``(category, time_of_day_band)`` —
into the Scheduler through ``SchedulerInput`` (axiom 05 "Evidence-affinity
term"). The scheduler stays pure: the app layer composes cells from the
pooled duration model (consent-gated, ADR-0007) and the per-user refinement
tier; the scheduler only reads them. Evidence biases *where* a task goes,
never *how long it is* — durations stay owned by the calibration pipeline
(axiom 17). Derivation is deterministic aggregation, never ML (ADR-0004).
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .common_types import TaskCategory
from .pooled_duration_model import TimeOfDayBand

#: Contract bounds for ``multiplier`` — the calibration clamp band shared by
#: pooled training and per-user refinement (``multiplier_min`` /
#: ``multiplier_max`` defaults).
EVIDENCE_MULTIPLIER_MIN = 0.5
EVIDENCE_MULTIPLIER_MAX = 2.0


class EvidenceSource(StrEnum):
    """Which evidence tier produced a cell.

    ``REVEALED`` cells aggregate the user's own drag-adjust /
    reconciliation-adoption observations
    (``docs/specs/placement-preference.schema.md``) — they state a location
    preference, never a duration claim, so they are multiplier-free.
    """

    POOLED = "pooled"
    PER_USER_REFINED = "per_user_refined"
    REVEALED = "revealed"


#: Sources whose cells state a duration multiplier for the band; any other
#: source (the revealed tier) must not carry one.
MULTIPLIER_SOURCES = frozenset(
    {EvidenceSource.POOLED, EvidenceSource.PER_USER_REFINED}
)


class EvidenceCell(BaseModel):
    """One ``(category, time_of_day_band)`` statement of band affinity."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    category: TaskCategory
    time_of_day_band: TimeOfDayBand
    multiplier: float | None = Field(
        default=None, ge=EVIDENCE_MULTIPLIER_MIN, le=EVIDENCE_MULTIPLIER_MAX
    )
    weighted_sample: float = Field(gt=0.0)
    source: EvidenceSource

    @model_validator(mode="after")
    def _multiplier_matches_source(self) -> EvidenceCell:
        if self.source in MULTIPLIER_SOURCES:
            if self.multiplier is None:
                raise ValueError(
                    f"{self.source.value} cell requires a multiplier"
                )
        elif self.multiplier is not None:
            raise ValueError(
                f"{self.source.value} cell must not carry a multiplier"
            )
        return self


class PlacementEvidence(BaseModel):
    """Per-user time-of-day evidence read by placement scoring (axiom 05).

    Empty by default: no evidence means placement scoring runs exactly as
    before — the evidence-affinity term is 0 for every candidate.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    cells: list[EvidenceCell] = Field(default_factory=list)

    @model_validator(mode="after")
    def _cells_unique(self) -> PlacementEvidence:
        keys = [
            (c.category.value, c.time_of_day_band.value, c.source.value)
            for c in self.cells
        ]
        if len(set(keys)) != len(keys):
            raise ValueError(
                "duplicate (category, time_of_day_band, source) cell"
            )
        return self
