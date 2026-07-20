"""Deterministic slot coverage and pathway fit (narrative-pathways NP-B).

The narrative equivalent of the ``prerequisites`` kernel: pure functions that
turn a :class:`UserProfile`'s confirmed evidence plus a :class:`PathwayTemplate`
into per-slot coverage and an overall fit count. No LLM output participates -
pathway fit, narrative gaps, and story progress are computed deterministically
from confirmed evidence (axiom 00). Fit is a slot *count*, never a score.

The item-to-slot join is intentionally the same case-insensitive comparison the
contracts use: both an item's ``theme_tags`` and a slot's ``required_themes_any``
are normalized through ``contracts._dedup.casefold_key`` so ``"Applied-ML"`` and
``"applied-ml"`` always join.

Assignment rule (spec 02-… §5): each evidence item is assigned to at most one
slot. A :class:`SlotOverride` on the profile's selection forces an item to a
named slot, but only when that selection targets *this* template (so ranking
coverage across other pathways is unaffected). Every other item is assigned to
the first slot, in template order, whose ``required_kinds`` contains the item's
``kind`` and whose ``required_themes_any`` intersects the item's ``theme_tags``.
That single pass realizes the "one item may fill only one slot; tie-break by
slot order then item order" contract.

This is a leaf kernel: it depends only on ``contracts/`` and ``common/``.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from agentic_calendar.contracts._dedup import casefold_key
from agentic_calendar.contracts.pathway_template import EvidenceSlot, PathwayTemplate
from agentic_calendar.contracts.user_profile import ExperienceItem, UserProfile


class SlotState(StrEnum):
    """Coverage state of one evidence slot, from confirmed evidence only."""

    FILLED = "filled"
    PARTIAL = "partial"
    EMPTY = "empty"


class SlotCoverage(BaseModel):
    """Derived coverage of one evidence slot. Every field is computed."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    slot_id: str
    state: SlotState
    matched_item_indices: tuple[int, ...] = Field(default_factory=tuple)
    """Indices into ``UserProfile.experience`` of the items assigned to this
    slot, in profile order. Positional identity avoids inventing an item id the
    contract does not carry; the list order is stable."""


class PathwayFit(BaseModel):
    """Derived fit of one pathway: filled-slot count, never a score."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    pathway_id: str
    filled_slots: int = Field(ge=0)
    total_slots: int = Field(ge=1)


def _item_matches_slot(item: ExperienceItem, slot: EvidenceSlot) -> bool:
    """Whether ``item`` is eligible for ``slot`` by kind and theme intersection."""
    if item.kind not in slot.required_kinds:
        return False
    item_themes = {casefold_key(t) for t in item.theme_tags}
    slot_themes = {casefold_key(t) for t in slot.required_themes_any}
    return not item_themes.isdisjoint(slot_themes)


def _override_slot_by_item(
    profile: UserProfile, template: PathwayTemplate, slot_ids: frozenset[str]
) -> dict[tuple[str, str], str]:
    """Map an overridden item identity to its forced ``slot_id``.

    Overrides apply only when the profile's selection is *this* template, so
    coverage computed for a non-selected pathway (card ranking) never picks them
    up. An override naming a slot the template does not have is ignored here; the
    service layer rejects it as ``UNKNOWN_EVIDENCE_SLOT``, and the kernel stays
    total.
    """
    selection = profile.pathway_selection
    if selection is None or selection.pathway_id != template.pathway_id:
        return {}
    return {
        (casefold_key(o.item_title), casefold_key(o.item_organization or "")): o.slot_id
        for o in selection.slot_overrides
        if o.slot_id in slot_ids
    }


def _assign_items(
    profile: UserProfile, template: PathwayTemplate
) -> dict[str, list[int]]:
    """Assign each experience item to at most one slot (see module docstring)."""
    slots = template.evidence_slots
    slot_ids = frozenset(s.slot_id for s in slots)
    overrides = _override_slot_by_item(profile, template, slot_ids)
    matched: dict[str, list[int]] = {s.slot_id: [] for s in slots}
    for index, item in enumerate(profile.experience):
        forced = overrides.get(
            (casefold_key(item.title), casefold_key(item.organization or ""))
        )
        if forced is not None:
            matched[forced].append(index)
            continue
        for slot in slots:
            if _item_matches_slot(item, slot):
                matched[slot.slot_id].append(index)
                break
    return matched


def _state_for(count: int, min_items: int) -> SlotState:
    if count >= min_items:
        return SlotState.FILLED
    if count >= 1:
        return SlotState.PARTIAL
    return SlotState.EMPTY


def slot_coverage(
    profile: UserProfile, template: PathwayTemplate
) -> tuple[SlotCoverage, ...]:
    """Per-slot coverage of ``template`` from ``profile``'s confirmed evidence.

    Returns one :class:`SlotCoverage` per slot, in template order.
    """
    matched = _assign_items(profile, template)
    return tuple(
        SlotCoverage(
            slot_id=slot.slot_id,
            state=_state_for(len(matched[slot.slot_id]), slot.min_items),
            matched_item_indices=tuple(matched[slot.slot_id]),
        )
        for slot in template.evidence_slots
    )


def pathway_fit(profile: UserProfile, template: PathwayTemplate) -> PathwayFit:
    """Overall fit of ``template``: how many slots are filled, out of the total.

    The card-ordering key (NP-D sorts by ``filled_slots`` descending, ties broken
    by registry order). No weights, no scores - if weighting is ever needed it
    enters ``tuning.toml`` like scheduler weights, never the LLM.
    """
    coverage = slot_coverage(profile, template)
    return PathwayFit(
        pathway_id=template.pathway_id,
        filled_slots=sum(1 for c in coverage if c.state is SlotState.FILLED),
        total_slots=len(template.evidence_slots),
    )
