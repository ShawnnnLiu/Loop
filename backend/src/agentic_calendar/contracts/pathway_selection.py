"""``pathway_selection`` contract.

Canonical spec: ``docs/specs/pathway-selection.schema.md``.

The user's explicit choice of one pathway - typed control-plane state stored
on the profile only via the existing confirm gate. Absent = the user skipped;
every downstream surface behaves exactly as today. Selection reaches the
Strategist as typed constraint extensions (``strategy_constraints``), never
as prose.

Coverage is always computed against the pinned ``pathway_registry_version``
until the user re-confirms on a newer one; a version the registry no longer
serves surfaces ``PATHWAY_REGISTRY_VERSION_MISMATCH``, never a silent re-map.
Registry membership of ``pathway_id`` / ``slot_id`` is a service-layer check
against that pinned version, not a contract-shape check.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SlotOverride(BaseModel):
    """One explicit item-to-slot assignment correcting the greedy default.

    The item is identified the way the profile identifies ``experience``
    entries: the case-insensitive ``(title, organization)`` pair.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    item_title: str = Field(min_length=1, max_length=120)
    item_organization: str | None = Field(default=None, min_length=1, max_length=120)
    slot_id: str = Field(min_length=1)


class PathwaySelection(BaseModel):
    """The user's confirmed pathway choice, pinned to a registry version."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    pathway_id: str = Field(min_length=1)
    pathway_registry_version: str = Field(min_length=1)
    selected_at: datetime
    slot_overrides: list[SlotOverride] = Field(default_factory=list)

    @model_validator(mode="after")
    def _selected_at_aware(self) -> PathwaySelection:
        if self.selected_at.tzinfo is None:
            raise ValueError("selected_at must be timezone-aware")
        return self

    @model_validator(mode="after")
    def _override_items_unique(self) -> PathwaySelection:
        keys = [
            (o.item_title.lower(), (o.item_organization or "").lower())
            for o in self.slot_overrides
        ]
        if len(set(keys)) != len(keys):
            dupes = sorted({k for k in keys if keys.count(k) > 1})
            raise ValueError(
                "slot_overrides must be unique by (item_title, item_organization), "
                f"case-insensitively - one item may fill only one slot; duplicates: {dupes}"
            )
        return self
