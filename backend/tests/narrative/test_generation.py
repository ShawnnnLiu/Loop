"""Deterministic knowledge-map generation (KT-B).

These tests double as the generator's acceptance suite: the KT-A ``KnowledgeMap``
contract invariants (unique ids, both-way membership, one capstone per slot) are
enforced by constructing the model, so a generated map that violates them raises
at build time. Here we pin determinism, the canonical ordering, branch
assignment, and every typed build-time failure.
"""

from __future__ import annotations

import pytest

from agentic_calendar.contracts.common_types import KnowledgeNodeKind
from agentic_calendar.contracts.pathway_template import EvidenceSlot, PathwayTemplate
from agentic_calendar.contracts.reason_codes import ReasonCode
from agentic_calendar.contracts.skill_grouping import (
    SkillGroup,
    SkillGrouping,
    SkillGroupingEntry,
)
from agentic_calendar.contracts.skill_taxonomy import SkillEntry, SkillTaxonomy
from agentic_calendar.narrative.generation import (
    CORE_BRANCH,
    MapGenerationError,
    generate_map,
)
from agentic_calendar.skill_taxonomy import load_skill_grouping, load_taxonomy
from agentic_calendar.templates import list_pathways
from tests.narrative._helpers import make_template

# --------------------------------------------------------------------------- #
# Small hand-built inputs for the failure paths.
# --------------------------------------------------------------------------- #


def _taxonomy(*skill_ids: str) -> SkillTaxonomy:
    return SkillTaxonomy(
        taxonomy_version="skill-taxonomy-v4",
        entries=[
            SkillEntry(
                skill_id=sid,
                display_name=sid.removeprefix("skill.").replace("-", " ").title(),
                aliases=[sid.removeprefix("skill.")],
                track_tags=["swe"],
                kind="concept",
            )
            for sid in skill_ids
        ],
    )


def _grouping(*entries: tuple[str, str, int]) -> SkillGrouping:
    group_ids = sorted({gid for _, gid, _ in entries})
    return SkillGrouping(
        skill_grouping_version="skill-grouping-v1",
        taxonomy_version="skill-taxonomy-v4",
        groups=[SkillGroup(group_id=gid, title=gid, blurb="b") for gid in group_ids],
        entries=[
            SkillGroupingEntry(skill_id=sid, group_id=gid, expected_minutes=m, blurb="b")
            for sid, gid, m in entries
        ],
    )


# --------------------------------------------------------------------------- #
# The real registry maps.
# --------------------------------------------------------------------------- #


def _real_maps():
    taxonomy = load_taxonomy()
    grouping = load_skill_grouping()
    return {p.pathway_id: generate_map(p, grouping, taxonomy) for p in list_pathways()}


def test_generation_is_deterministic_and_byte_identical() -> None:
    taxonomy = load_taxonomy()
    grouping = load_skill_grouping()
    for pathway in list_pathways():
        first = generate_map(pathway, grouping, taxonomy)
        second = generate_map(pathway, grouping, taxonomy)
        assert first == second
        assert first.model_dump_json() == second.model_dump_json()


def test_every_slot_gets_exactly_one_capstone() -> None:
    for pathway in list_pathways():
        kmap = _real_maps()[pathway.pathway_id]
        capstone_slots = sorted(
            n.evidence_slot_id
            for n in kmap.nodes
            if n.kind is KnowledgeNodeKind.CAPSTONE
        )
        assert capstone_slots == sorted(s.slot_id for s in pathway.evidence_slots)


def test_skill_nodes_stay_under_the_ceiling() -> None:
    for pid, kmap in _real_maps().items():
        skill_nodes = [n for n in kmap.nodes if n.kind is KnowledgeNodeKind.SKILL]
        assert len(skill_nodes) <= 40, pid


def test_skill_node_ids_are_kn_prefixed_from_the_skill_suffix() -> None:
    for kmap in _real_maps().values():
        for node in kmap.nodes:
            if node.kind is KnowledgeNodeKind.SKILL:
                assert node.skill_id is not None
                assert node.node_id == "kn-" + node.skill_id.removeprefix("skill.")


def test_groups_are_canonically_ordered_core_first() -> None:
    for kmap in _real_maps().values():
        core = [g for g in kmap.groups if g.branch == CORE_BRANCH]
        # All core groups precede every non-core group.
        first_non_core = next(
            (i for i, g in enumerate(kmap.groups) if g.branch != CORE_BRANCH),
            len(kmap.groups),
        )
        assert all(kmap.groups.index(g) < first_non_core for g in core)


def test_a_group_seeded_by_two_slots_becomes_core() -> None:
    # full-stack seeds git+code-review (public/polish) and ci-cd/testing across
    # slots, so kg-cicd is seeded by more than one slot -> core.
    full_stack = _real_maps()["full-stack-product-engineer"]
    cicd = next(g for g in full_stack.groups if g.group_id == "kg-cicd")
    assert cicd.branch == CORE_BRANCH


def test_a_group_seeded_by_one_slot_takes_that_slots_branch() -> None:
    backend = _real_maps()["backend-infrastructure-engineer"]
    # kg-databases-relational is only seeded by the data-layer slot.
    rel = next(g for g in backend.groups if g.group_id == "kg-databases-relational")
    assert rel.branch == "data-layer"


def test_included_group_pulls_all_its_rowed_members() -> None:
    # A slot seeding one member of a group pulls the group's other members too.
    taxonomy = _taxonomy("skill.a", "skill.b", "skill.c")
    grouping = _grouping(("skill.a", "kg-x", 60), ("skill.b", "kg-x", 60), ("skill.c", "kg-y", 60))
    template = PathwayTemplate(
        pathway_id="p",
        pathway_schema_version="pathway-template-v1",
        career_track="swe",
        display_name="P",
        spine="s.",
        audience_note="a.",
        evidence_slots=[
            EvidenceSlot(
                slot_id="only",
                title="Only",
                required_kinds=["work"],
                required_themes_any=["backend-systems"],
                gap_module_hint="h",
                branch_skill_ids=["skill.a"],  # pulls kg-x (a + b), not kg-y
            )
        ],
    )
    kmap = generate_map(template, grouping, taxonomy)
    skill_ids = {n.skill_id for n in kmap.nodes if n.kind is KnowledgeNodeKind.SKILL}
    assert skill_ids == {"skill.a", "skill.b"}


def test_missing_grouping_row_raises_skill_grouping_missing_entry() -> None:
    taxonomy = _taxonomy("skill.a")
    grouping = _grouping(("skill.other", "kg-x", 60))  # no row for skill.a
    template = make_template()  # seeds skill.python (also unrowed here)
    with pytest.raises(MapGenerationError) as exc:
        generate_map(template, grouping, taxonomy)
    assert exc.value.reason_code is ReasonCode.SKILL_GROUPING_MISSING_ENTRY


def test_over_ceiling_raises_budget_exceeded() -> None:
    ids = [f"skill.s{i}" for i in range(6)]
    taxonomy = _taxonomy(*ids)
    grouping = _grouping(*[(sid, "kg-big", 60) for sid in ids])
    template = PathwayTemplate(
        pathway_id="p",
        pathway_schema_version="pathway-template-v1",
        career_track="swe",
        display_name="P",
        spine="s.",
        audience_note="a.",
        evidence_slots=[
            EvidenceSlot(
                slot_id="only",
                title="Only",
                required_kinds=["work"],
                required_themes_any=["backend-systems"],
                gap_module_hint="h",
                branch_skill_ids=["skill.s0"],
            )
        ],
    )
    with pytest.raises(MapGenerationError) as exc:
        generate_map(template, grouping, taxonomy, ceiling=5)
    assert exc.value.reason_code is ReasonCode.KNOWLEDGE_MAP_BUDGET_EXCEEDED


def test_empty_seed_list_raises_slot_seeds_missing() -> None:
    # Defense-in-depth: the contract forbids an empty seed list, so bypass it
    # with model_construct to exercise the generator's guard.
    slot = EvidenceSlot.model_construct(
        slot_id="only",
        title="Only",
        required_kinds=["work"],
        required_themes_any=["backend-systems"],
        gap_module_hint="h",
        branch_skill_ids=[],
    )
    template = PathwayTemplate.model_construct(
        pathway_id="p",
        pathway_schema_version="pathway-template-v1",
        career_track="swe",
        display_name="P",
        spine="s.",
        audience_note="a.",
        evidence_slots=[slot],
        knowledge_map=None,
    )
    with pytest.raises(MapGenerationError) as exc:
        generate_map(template, _grouping(("skill.a", "kg-x", 60)), _taxonomy("skill.a"))
    assert exc.value.reason_code is ReasonCode.SLOT_SEEDS_MISSING
