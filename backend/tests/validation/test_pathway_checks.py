"""Tests for narrative-pathway slot-linkage validation (NP-D).

The three checks that need external state - the selected pathway template and
the ``max_slot_modules`` bound - so they live in the validation layer, not on
the ``SyllabusModule`` contract. Failures route to a Strategist repair.
"""

from __future__ import annotations

from datetime import UTC, datetime

from agentic_calendar.contracts.reason_codes import ReasonCode
from agentic_calendar.contracts.validation_result import ArtifactType, NextAction
from agentic_calendar.contracts.violation_types import ViolationType
from agentic_calendar.validation import validate_syllabus_units
from agentic_calendar.validation.pathway import check_pathway_slots
from tests.narrative._helpers import make_template, slot_linked_syllabus

_TEMPLATE = make_template()  # slots s1, s2, s3


def _types(syllabus, *, template, limit=3) -> list[ViolationType]:
    return [
        v.type
        for v in check_pathway_slots(
            syllabus, selected_pathway=template, max_slot_modules=limit
        )
    ]


# --------------------------------------------------------------------------- #
# check_pathway_slots (unit)
# --------------------------------------------------------------------------- #


def test_no_violations_when_links_resolve_within_limit() -> None:
    syllabus = slot_linked_syllabus(["s1", "s2", None])
    assert _types(syllabus, template=_TEMPLATE) == []


def test_unlinked_modules_never_flag_even_without_selection() -> None:
    syllabus = slot_linked_syllabus([None, None])
    assert _types(syllabus, template=None) == []


def test_slot_link_without_selection_is_pathway_not_selected() -> None:
    syllabus = slot_linked_syllabus(["s1", None])
    assert _types(syllabus, template=None) == [ViolationType.PATHWAY_NOT_SELECTED]


def test_unknown_slot_id_is_flagged() -> None:
    syllabus = slot_linked_syllabus(["s1", "does-not-exist"])
    assert _types(syllabus, template=_TEMPLATE) == [ViolationType.UNKNOWN_EVIDENCE_SLOT]


def test_over_limit_is_flagged_once_for_the_whole_syllabus() -> None:
    syllabus = slot_linked_syllabus(["s1", "s2"])
    types = _types(syllabus, template=_TEMPLATE, limit=1)
    assert types == [ViolationType.SLOT_MODULE_LIMIT_EXCEEDED]


def test_violation_details_carry_repairable_context() -> None:
    syllabus = slot_linked_syllabus(["missing"])
    (violation,) = check_pathway_slots(
        syllabus, selected_pathway=_TEMPLATE, max_slot_modules=3
    )
    assert violation.module_id == "m0"
    assert violation.details["evidence_slot_id"] == "missing"
    assert violation.details["pathway_id"] == _TEMPLATE.pathway_id


# --------------------------------------------------------------------------- #
# validate_syllabus_units (integration: reason code + repair routing)
# --------------------------------------------------------------------------- #


def _validate(syllabus, *, template, limit=3, repair_attempt=0):
    return validate_syllabus_units(
        syllabus,
        claim_registry={},
        now=datetime(2026, 7, 20, tzinfo=UTC),
        run_id="run-1",
        selected_pathway=template,
        max_slot_modules=limit,
        repair_attempt=repair_attempt,
    )


def test_valid_slot_linked_syllabus_passes() -> None:
    result = _validate(slot_linked_syllabus(["s1", None]), template=_TEMPLATE)
    assert result.valid
    assert result.artifact_type is ArtifactType.SYLLABUS_UNITS
    assert result.reason_code is None


def test_pathway_not_selected_routes_to_strategist_repair() -> None:
    result = _validate(slot_linked_syllabus(["s1"]), template=None)
    assert not result.valid
    assert result.reason_code is ReasonCode.PATHWAY_NOT_SELECTED
    assert result.next_action is NextAction.STRATEGIST_REPAIR_RETRY


def test_unknown_slot_summarizes_to_unknown_evidence_slot() -> None:
    result = _validate(slot_linked_syllabus(["nope"]), template=_TEMPLATE)
    assert result.reason_code is ReasonCode.UNKNOWN_EVIDENCE_SLOT


def test_over_limit_summarizes_to_slot_module_limit_exceeded() -> None:
    result = _validate(slot_linked_syllabus(["s1", "s2"]), template=_TEMPLATE, limit=1)
    assert result.reason_code is ReasonCode.SLOT_MODULE_LIMIT_EXCEEDED


def test_selection_missing_wins_over_limit_in_summary() -> None:
    # Two links, no selection, limit 1: both PATHWAY_NOT_SELECTED (x2) and
    # SLOT_MODULE_LIMIT_EXCEEDED fire; the most fundamental code surfaces.
    result = _validate(slot_linked_syllabus(["s1", "s2"]), template=None, limit=1)
    assert result.reason_code is ReasonCode.PATHWAY_NOT_SELECTED


def test_repair_limit_exhaustion_routes_to_user() -> None:
    result = _validate(slot_linked_syllabus(["nope"]), template=_TEMPLATE, repair_attempt=2)
    assert result.next_action is NextAction.ERROR_REQUIRES_USER
