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
from agentic_calendar.validation.pathway import (
    check_knowledge_node_tags,
    check_mastery_review,
    check_pathway_slots,
)
from tests.narrative._helpers import (
    make_template,
    mastery_tagged_syllabus,
    node_tagged_syllabus,
    slot_linked_syllabus,
)

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


# --------------------------------------------------------------------------- #
# check_knowledge_node_tags (KT-C: unit)
# --------------------------------------------------------------------------- #

_VOCAB = ["kn-rag", "kn-embeddings"]


def _node_types(syllabus, *, vocab) -> list[ViolationType]:
    return [
        v.type
        for v in check_knowledge_node_tags(syllabus, knowledge_node_ids=vocab)
    ]


def test_tags_within_vocabulary_pass() -> None:
    syllabus = node_tagged_syllabus([["kn-rag"], ["kn-embeddings", "kn-rag"], []])
    assert _node_types(syllabus, vocab=_VOCAB) == []


def test_untagged_modules_pass_without_vocabulary() -> None:
    syllabus = node_tagged_syllabus([[], []])
    assert _node_types(syllabus, vocab=[]) == []


def test_tag_outside_vocabulary_is_unknown_knowledge_node() -> None:
    syllabus = node_tagged_syllabus([["kn-not-on-map"]])
    assert _node_types(syllabus, vocab=_VOCAB) == [
        ViolationType.UNKNOWN_KNOWLEDGE_NODE
    ]


def test_any_tag_rejected_when_no_pathway_gives_empty_vocabulary() -> None:
    syllabus = node_tagged_syllabus([["kn-rag"]])
    assert _node_types(syllabus, vocab=[]) == [ViolationType.UNKNOWN_KNOWLEDGE_NODE]


def test_one_violation_per_offending_tag() -> None:
    syllabus = node_tagged_syllabus([["kn-rag", "kn-x", "kn-y"]])
    violations = check_knowledge_node_tags(syllabus, knowledge_node_ids=_VOCAB)
    assert [v.details["knowledge_node_id"] for v in violations] == ["kn-x", "kn-y"]
    assert {v.module_id for v in violations} == {"m0"}


# --------------------------------------------------------------------------- #
# validate_syllabus_units (KT-C: reason code + repair routing)
# --------------------------------------------------------------------------- #


def test_unknown_node_tag_summarizes_to_unknown_knowledge_node() -> None:
    result = validate_syllabus_units(
        node_tagged_syllabus([["kn-not-on-map"]]),
        claim_registry={},
        now=datetime(2026, 7, 20, tzinfo=UTC),
        run_id="run-1",
        knowledge_node_ids=_VOCAB,
    )
    assert not result.valid
    assert result.reason_code is ReasonCode.UNKNOWN_KNOWLEDGE_NODE
    assert result.next_action is NextAction.STRATEGIST_REPAIR_RETRY


def test_valid_node_tags_pass_through_validation() -> None:
    result = validate_syllabus_units(
        node_tagged_syllabus([["kn-rag"], []]),
        claim_registry={},
        now=datetime(2026, 7, 20, tzinfo=UTC),
        run_id="run-1",
        knowledge_node_ids=_VOCAB,
    )
    assert result.valid
    assert result.reason_code is None


# --------------------------------------------------------------------------- #
# check_mastery_review (MM-C: unit)
# --------------------------------------------------------------------------- #

_MASTERED = ["kn-rag"]
_REVIEW = ["kn-embeddings"]


def _mastery_types(
    syllabus,
    *,
    mastered=_MASTERED,
    review=_REVIEW,
    max_modules=2,
    max_minutes=60,
) -> list[ViolationType]:
    return [
        v.type
        for v in check_mastery_review(
            syllabus,
            mastered_node_ids=mastered,
            review_node_ids=review,
            max_review_modules=max_modules,
            max_review_minutes=max_minutes,
        )
    ]


def test_untagged_module_is_never_a_review_module() -> None:
    # An untagged module trains no specific skill; the mastery instruction is
    # advisory, so it is never review-bounded even at zero minutes budget.
    syllabus = mastery_tagged_syllabus([([], 600)])
    assert _mastery_types(syllabus, max_minutes=1) == []


def test_mixed_module_is_unbounded() -> None:
    # A module that also trains an unmastered skill is legitimate new work.
    syllabus = mastery_tagged_syllabus([(["kn-rag", "kn-new-work"], 600)])
    assert _mastery_types(syllabus) == []


def test_all_mastered_review_module_within_bounds_passes() -> None:
    syllabus = mastery_tagged_syllabus([(["kn-rag"], 45), (["kn-embeddings"], 60)])
    assert _mastery_types(syllabus) == []


def test_review_module_over_minutes_is_bound_exceeded() -> None:
    syllabus = mastery_tagged_syllabus([(["kn-rag"], 90)])
    assert _mastery_types(syllabus) == [ViolationType.MASTERY_REVIEW_BOUND_EXCEEDED]


def test_review_and_mastered_tags_mix_still_counts_as_review() -> None:
    # A module tagged with a mastered node AND a review node is all-old-skill.
    syllabus = mastery_tagged_syllabus([(["kn-rag", "kn-embeddings"], 120)])
    assert _mastery_types(syllabus) == [ViolationType.MASTERY_REVIEW_BOUND_EXCEEDED]


def test_too_many_review_modules_is_limit_exceeded() -> None:
    syllabus = mastery_tagged_syllabus(
        [(["kn-rag"], 30), (["kn-embeddings"], 30), (["kn-rag"], 30)]
    )
    assert _mastery_types(syllabus, max_modules=2) == [
        ViolationType.REVIEW_MODULE_LIMIT_EXCEEDED
    ]


def test_empty_mastery_lists_make_the_gate_inert() -> None:
    # No mastery data ⇒ no node is a review target ⇒ nothing is bounded.
    syllabus = mastery_tagged_syllabus([(["kn-rag"], 600)])
    assert _mastery_types(syllabus, mastered=[], review=[], max_minutes=1) == []


def test_bound_violation_carries_repairable_context() -> None:
    (violation,) = check_mastery_review(
        mastery_tagged_syllabus([(["kn-rag"], 90)]),
        mastered_node_ids=_MASTERED,
        review_node_ids=_REVIEW,
        max_review_modules=2,
        max_review_minutes=60,
    )
    assert violation.module_id == "m0"
    assert violation.details["estimated_total_min"] == 90
    assert violation.details["max_review_minutes"] == 60


# --------------------------------------------------------------------------- #
# validate_syllabus_units (MM-C: reason code + repair routing)
# --------------------------------------------------------------------------- #


def _validate_mastery(syllabus, *, max_modules=2, max_minutes=60):
    return validate_syllabus_units(
        syllabus,
        claim_registry={},
        now=datetime(2026, 7, 20, tzinfo=UTC),
        run_id="run-1",
        knowledge_node_ids=_VOCAB,
        mastered_node_ids=_MASTERED,
        review_node_ids=_REVIEW,
        max_review_modules=max_modules,
        max_review_minutes=max_minutes,
    )


def test_over_length_review_summarizes_to_mastery_review_bound() -> None:
    result = _validate_mastery(mastery_tagged_syllabus([(["kn-rag"], 90)]))
    assert not result.valid
    assert result.reason_code is ReasonCode.MASTERY_REVIEW_BOUND_EXCEEDED
    assert result.next_action is NextAction.STRATEGIST_REPAIR_RETRY


def test_too_many_reviews_summarizes_to_review_module_limit() -> None:
    result = _validate_mastery(
        mastery_tagged_syllabus(
            [(["kn-rag"], 30), (["kn-embeddings"], 30), (["kn-rag"], 30)]
        ),
        max_modules=2,
    )
    assert result.reason_code is ReasonCode.REVIEW_MODULE_LIMIT_EXCEEDED


def test_per_module_bound_wins_over_aggregate_limit_in_summary() -> None:
    # Three over-length review modules trip both codes; the narrower per-module
    # bound surfaces (mirrors the slot codes' per-module-before-aggregate order).
    result = _validate_mastery(
        mastery_tagged_syllabus(
            [(["kn-rag"], 90), (["kn-embeddings"], 90), (["kn-rag"], 90)]
        ),
        max_modules=2,
    )
    assert result.reason_code is ReasonCode.MASTERY_REVIEW_BOUND_EXCEEDED


def test_bounded_review_passes_through_validation() -> None:
    # One short all-mastered review module + one long mixed module (mastered +
    # an unmastered vocab node) — the mixed one is unbounded new work.
    result = validate_syllabus_units(
        mastery_tagged_syllabus([(["kn-rag"], 45), (["kn-rag", "kn-new-work"], 200)]),
        claim_registry={},
        now=datetime(2026, 7, 20, tzinfo=UTC),
        run_id="run-1",
        knowledge_node_ids=[*_VOCAB, "kn-new-work"],
        mastered_node_ids=_MASTERED,
        review_node_ids=_REVIEW,
    )
    assert result.valid
    assert result.reason_code is None
