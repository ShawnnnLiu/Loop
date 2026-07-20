"""Deterministic story progress (narrative-pathways NP-B).

``story_progress`` overlays the active plan onto slot coverage: a slot is
*filled* when confirmed evidence covers it (``slot_coverage``), and *in progress*
when an active-plan module carries that slot's ``evidence_slot_id``. Both signals
are reported truthfully; how they collapse for display is the frontend's call
(NP-E). Module linkage is opaque metadata - nothing schedules differently because
of story state (the Planner and Scheduler never see it).

Leaf kernel: depends only on ``contracts/`` and ``common/``.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from agentic_calendar.contracts.pathway_template import PathwayTemplate
from agentic_calendar.contracts.syllabus_units import SyllabusUnits
from agentic_calendar.contracts.user_profile import UserProfile

from .coverage import SlotState, slot_coverage


class SlotProgress(BaseModel):
    """Derived story progress of one slot: coverage plus active-plan linkage."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    slot_id: str
    state: SlotState
    """Coverage state from confirmed evidence (``slot_coverage``)."""
    matched_item_indices: tuple[int, ...] = Field(default_factory=tuple)
    in_progress: bool
    """Whether an active-plan module carries this slot's ``evidence_slot_id``."""


def story_progress(
    profile: UserProfile, syllabus: SyllabusUnits, template: PathwayTemplate
) -> tuple[SlotProgress, ...]:
    """Per-slot story progress of ``template``, in template order.

    ``in_progress`` is set when any module of ``syllabus`` links to the slot via
    ``evidence_slot_id``; ``state`` remains the confirmed-evidence coverage.
    """
    module_slot_ids = {
        module.evidence_slot_id
        for module in syllabus.modules
        if module.evidence_slot_id is not None
    }
    return tuple(
        SlotProgress(
            slot_id=coverage.slot_id,
            state=coverage.state,
            matched_item_indices=coverage.matched_item_indices,
            in_progress=coverage.slot_id in module_slot_ids,
        )
        for coverage in slot_coverage(profile, template)
    )
