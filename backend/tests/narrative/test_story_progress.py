"""Story progress = coverage overlaid with active-plan slot linkage (NP-B)."""

from __future__ import annotations

from agentic_calendar.contracts.common_types import EvidenceKind
from agentic_calendar.narrative import SlotState, story_progress

from ._helpers import item, make_profile, make_template, slot_linked_syllabus


def _by_id(progress: tuple, slot_id: str):
    return next(p for p in progress if p.slot_id == slot_id)


def test_module_linkage_marks_slot_in_progress() -> None:
    profile = make_profile([])  # no evidence yet
    syllabus = slot_linked_syllabus(["s2", None])
    progress = story_progress(profile, syllabus, make_template())
    assert _by_id(progress, "s2").in_progress is True
    assert _by_id(progress, "s2").state is SlotState.EMPTY
    assert _by_id(progress, "s1").in_progress is False


def test_filled_coverage_and_in_progress_are_both_reported() -> None:
    profile = make_profile([item("Thing", EvidenceKind.PROJECT, ["alpha"])])  # fills s1
    syllabus = slot_linked_syllabus(["s1"])
    progress = story_progress(profile, syllabus, make_template())
    s1 = _by_id(progress, "s1")
    assert s1.state is SlotState.FILLED
    assert s1.in_progress is True
    assert s1.matched_item_indices == (0,)


def test_no_linked_modules_leaves_everything_not_in_progress() -> None:
    profile = make_profile([item("Thing", EvidenceKind.PROJECT, ["alpha"])])
    syllabus = slot_linked_syllabus([None, None])
    progress = story_progress(profile, syllabus, make_template())
    assert all(p.in_progress is False for p in progress)
    assert _by_id(progress, "s1").state is SlotState.FILLED


def test_progress_preserves_template_slot_order() -> None:
    progress = story_progress(make_profile([]), slot_linked_syllabus([None]), make_template())
    assert [p.slot_id for p in progress] == ["s1", "s2", "s3"]
