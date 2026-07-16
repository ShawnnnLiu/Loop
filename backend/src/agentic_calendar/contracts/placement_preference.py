"""``placement_preference`` contract.

Canonical spec: ``docs/specs/placement-preference.schema.md``.

A :class:`PlacementPreferenceObservation` is the append-only record of one
user action that states a preferred time-of-day: a drag-to-adjust move
applied by ``CycleService.adjust`` or an external edit adopted by
``CycleService.reconcile``. Rows are stored per observation — never
pre-aggregated — so recency windows stay a pure read-time computation; the
app layer folds qualifying groups into ``revealed`` evidence cells (axiom
05 "Revealed-preference term"). Deterministic counting only, no ML
(ADR-0004); ``task_id`` and enums only, never raw calendar event titles
(axiom 06).

``observation_id`` uniqueness / dedup is a store concern, not a
single-object invariant (same split as ``task_disposition``).
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .common_types import TaskCategory
from .pooled_duration_model import TimeOfDayBand


class PlacementPreferenceSource(StrEnum):
    """Which user action produced the observation."""

    DRAG_ADJUST = "drag_adjust"
    """A drag-to-adjust move that passed server-side re-validation and was
    applied to the pending draft."""
    RECONCILE_ADOPT = "reconcile_adopt"
    """An external calendar move/resize adopted by inbound reconciliation
    (disposition ``ADOPTED`` — never a rejected move, never a deletion)."""


class PlacementPreferenceObservation(BaseModel):
    """One user repositioning of a task into a time-of-day band."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    observation_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    category: TaskCategory
    time_of_day_band: TimeOfDayBand
    observed_at: datetime
    source: PlacementPreferenceSource

    @model_validator(mode="after")
    def _observed_at_aware(self) -> PlacementPreferenceObservation:
        if self.observed_at.tzinfo is None:
            raise ValueError(
                "placement preference observed_at must be timezone-aware"
            )
        return self
