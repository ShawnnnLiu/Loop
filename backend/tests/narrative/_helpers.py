"""Shared builders for the ``narrative/`` kernel tests.

Profiles are built by loading a valid ``user_profile`` fixture and overriding
just the fields the kernel reads (``experience`` + ``pathway_selection``), so the
rest of the profile stays contract-valid without restating every required field.
"""

from __future__ import annotations

from typing import Any

from agentic_calendar.contracts.career_track import CareerTrack
from agentic_calendar.contracts.common_types import EvidenceKind, Priority
from agentic_calendar.contracts.pathway_template import EvidenceSlot, PathwayTemplate
from agentic_calendar.contracts.syllabus_units import SyllabusModule, SyllabusUnits
from agentic_calendar.contracts.user_profile import UserProfile
from tests._fixture_loader import iter_valid

TEST_PATHWAY_ID = "test-pathway"


def make_profile(
    experience: list[dict[str, Any]],
    pathway_selection: dict[str, Any] | None = None,
) -> UserProfile:
    """Build a valid profile with the given evidence and optional selection."""
    payload = dict(next(iter_valid("user_profile")).payload)
    payload["experience"] = experience
    if pathway_selection is None:
        payload.pop("pathway_selection", None)
    else:
        payload["pathway_selection"] = pathway_selection
    return UserProfile.model_validate(payload)


def item(
    title: str,
    kind: EvidenceKind,
    themes: list[str],
    organization: str | None = None,
) -> dict[str, Any]:
    """One evidence-item payload."""
    payload: dict[str, Any] = {"title": title, "kind": kind.value, "theme_tags": themes}
    if organization is not None:
        payload["organization"] = organization
    return payload


def selection(
    slot_overrides: list[dict[str, str]] | None = None,
    pathway_id: str = TEST_PATHWAY_ID,
) -> dict[str, Any]:
    """A pathway-selection payload pinned to the test registry version."""
    return {
        "pathway_id": pathway_id,
        "pathway_registry_version": "pathway-registry-v1",
        "selected_at": "2026-07-19T12:00:00-07:00",
        "slot_overrides": slot_overrides or [],
    }


def make_template(pathway_id: str = TEST_PATHWAY_ID) -> PathwayTemplate:
    """A three-slot template with deliberate kind/theme overlap for tie-breaks.

    ``s1`` and ``s2`` both accept a ``project`` tagged ``alpha`` - the item must
    land in ``s1`` (earlier in registry order). ``s3`` needs two items.
    """
    return PathwayTemplate(
        pathway_id=pathway_id,
        pathway_schema_version="pathway-template-v1",
        career_track=CareerTrack.SWE,
        display_name="Test",
        spine="A test spine.",
        audience_note="Test audience.",
        evidence_slots=[
            EvidenceSlot(
                slot_id="s1",
                title="Slot one",
                required_kinds=[EvidenceKind.WORK, EvidenceKind.PROJECT],
                required_themes_any=["alpha"],
                gap_module_hint="hint",
                branch_skill_ids=["skill.python"],
            ),
            EvidenceSlot(
                slot_id="s2",
                title="Slot two",
                required_kinds=[EvidenceKind.PROJECT],
                required_themes_any=["alpha", "beta"],
                gap_module_hint="hint",
                branch_skill_ids=["skill.python"],
            ),
            EvidenceSlot(
                slot_id="s3",
                title="Slot three",
                required_kinds=[EvidenceKind.WORK],
                required_themes_any=["gamma"],
                min_items=2,
                gap_module_hint="hint",
                branch_skill_ids=["skill.python"],
            ),
        ],
    )


def slot_linked_syllabus(slot_ids: list[str | None]) -> SyllabusUnits:
    """A syllabus whose modules link to the given slot ids (``None`` = unlinked)."""
    modules = [
        SyllabusModule(
            module_id=f"m{i}",
            title=f"Module {i}",
            priority=Priority.MEDIUM,
            reason="builds toward the pillar" if slot_id is not None else None,
            target_outcomes=["outcome"],
            estimated_total_min=60,
            difficulty=2,
            evidence_slot_id=slot_id,
        )
        for i, slot_id in enumerate(slot_ids)
    ]
    return SyllabusUnits(
        syllabus_version="syllabus-v1",
        goal_summary="Test goal.",
        modules=modules,
    )


def node_tagged_syllabus(tag_lists: list[list[str]]) -> SyllabusUnits:
    """A syllabus whose modules tag the given ``knowledge_node_ids`` (KT-C)."""
    return mastery_tagged_syllabus([(tags, 60) for tags in tag_lists])


def mastery_tagged_syllabus(
    modules: list[tuple[list[str], int]],
) -> SyllabusUnits:
    """A syllabus of ``(knowledge_node_ids, estimated_total_min)`` modules (MM-C).

    Lets a test set both a module's tags and its minutes, which the mastery
    output gate reads together (an all-mastered module over the minutes cap is a
    ``MASTERY_REVIEW_BOUND_EXCEEDED``).
    """
    return SyllabusUnits(
        syllabus_version="syllabus-v1",
        goal_summary="Test goal.",
        modules=[
            SyllabusModule(
                module_id=f"m{i}",
                title=f"Module {i}",
                priority=Priority.MEDIUM,
                reason=None,
                target_outcomes=["outcome"],
                estimated_total_min=minutes,
                difficulty=2,
                knowledge_node_ids=tags,
            )
            for i, (tags, minutes) in enumerate(modules)
        ],
    )
