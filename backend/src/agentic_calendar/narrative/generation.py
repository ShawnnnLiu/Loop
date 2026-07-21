"""Deterministic knowledge-map generation (narrative-pathways KT-B).

``generate_map`` is a pure function from a :class:`PathwayTemplate`'s slot seeds
plus the curated :class:`SkillGrouping` and pinned :class:`SkillTaxonomy` to a
:class:`KnowledgeMap` (``07-tree-generation.md``). Generation reduces to
membership lookup - there are no edges, no closure, no cycles: each slot's seed
skills name their groups, each included group brings all its member skills, and
one branch-level capstone heads each evidence slot.

Every bound violation is a loud typed failure (:class:`MapGenerationError`
carrying a build-time :class:`ReasonCode`), never a silent placement or prune.
The build-time tool (``tools/generate_knowledge_maps.py``) writes the committed
artifact; nothing generates a map at runtime.

Leaf kernel: depends only on ``contracts`` and ``common``.
"""

from __future__ import annotations

from agentic_calendar.common.errors import AgenticCalendarError
from agentic_calendar.contracts.common_types import KnowledgeNodeKind
from agentic_calendar.contracts.knowledge_map import (
    KnowledgeGroup,
    KnowledgeMap,
    KnowledgeNode,
)
from agentic_calendar.contracts.pathway_template import PathwayTemplate
from agentic_calendar.contracts.reason_codes import ReasonCode
from agentic_calendar.contracts.skill_grouping import SkillGrouping, SkillGroupingEntry
from agentic_calendar.contracts.skill_taxonomy import SkillTaxonomy

#: The skill-node ceiling per generated map (``06-…`` d4). Loop default; Tandem
#: raises it to 60. A heuristic prior, not a calibrated threshold.
LOOP_SKILL_NODE_CEILING = 40

#: Below this many skill nodes a map is advisory-thin (``07-…`` step 6) - the
#: build tool logs it, never a failure.
ADVISORY_MIN_SKILL_NODES = 20

#: Branch value for a group seeded by two or more slots (``07-…`` step 3).
CORE_BRANCH = "core"


class MapGenerationError(AgenticCalendarError):
    """A build-time generation invariant was violated.

    Carries the typed :class:`ReasonCode` and a human-readable ``detail`` so the
    ``tools/`` CLI can report it; these codes can never occur at runtime
    (``07-tree-generation.md``).
    """

    def __init__(self, reason_code: ReasonCode, detail: str) -> None:
        self.reason_code = reason_code
        self.detail = detail
        super().__init__(f"{reason_code.value}: {detail}")


def _node_id_for(skill_id: str) -> str:
    """``skill.rag`` -> ``kn-rag`` (``07-…`` step 5). Skill ids are already
    ``[a-z0-9-]`` after the ``skill.`` prefix, so the result matches ``^kn-``."""
    return "kn-" + skill_id.removeprefix("skill.")


def generate_map(
    template: PathwayTemplate,
    grouping: SkillGrouping,
    taxonomy: SkillTaxonomy,
    *,
    ceiling: int = LOOP_SKILL_NODE_CEILING,
) -> KnowledgeMap:
    """Emit the deterministic :class:`KnowledgeMap` for ``template``.

    Raises :class:`MapGenerationError` with the appropriate build-time
    :class:`ReasonCode` on a missing seed list, an unrowed seed skill, or a map
    over the skill-node ``ceiling``. Same inputs always produce an equal map with
    a byte-identical serialization (canonical ordering, no timestamps).
    """
    display_by_skill = {e.skill_id: e.display_name for e in taxonomy.entries}
    entry_by_skill = {e.skill_id: e for e in grouping.entries}
    group_by_id = {g.group_id: g for g in grouping.groups}
    slot_index = {s.slot_id: i for i, s in enumerate(template.evidence_slots)}

    # Steps 1 + 3: resolve seeds to groups; record which slots seed each group.
    seeded_by: dict[str, set[str]] = {}
    for slot in template.evidence_slots:
        if not slot.branch_skill_ids:  # defense-in-depth; contract requires >= 1
            raise MapGenerationError(
                ReasonCode.SLOT_SEEDS_MISSING,
                f"{template.pathway_id}: slot {slot.slot_id!r} has no branch_skill_ids",
            )
        for seed in slot.branch_skill_ids:
            entry = entry_by_skill.get(seed)
            if entry is None:
                raise MapGenerationError(
                    ReasonCode.SKILL_GROUPING_MISSING_ENTRY,
                    f"{template.pathway_id}: seed {seed!r} (slot {slot.slot_id!r}) "
                    "has no skill-grouping row",
                )
            seeded_by.setdefault(entry.group_id, set()).add(slot.slot_id)

    included_group_ids = set(seeded_by)

    # Step 2: an included group brings all its member skills (each has a row).
    members: dict[str, list[SkillGroupingEntry]] = {}
    for entry in grouping.entries:
        if entry.group_id in included_group_ids:
            members.setdefault(entry.group_id, []).append(entry)

    # Step 5: skill nodes; member ids recorded in the same canonical order.
    skill_nodes: list[KnowledgeNode] = []
    member_node_ids: dict[str, list[str]] = {gid: [] for gid in included_group_ids}
    for gid in included_group_ids:
        for entry in sorted(members[gid], key=lambda e: e.skill_id):
            title = display_by_skill.get(entry.skill_id)
            if title is None:
                raise MapGenerationError(
                    ReasonCode.SKILL_GROUPING_MISSING_ENTRY,
                    f"{template.pathway_id}: grouping skill {entry.skill_id!r} does "
                    f"not resolve against taxonomy {taxonomy.taxonomy_version}",
                )
            node_id = _node_id_for(entry.skill_id)
            skill_nodes.append(
                KnowledgeNode(
                    node_id=node_id,
                    title=title,
                    kind=KnowledgeNodeKind.SKILL,
                    skill_id=entry.skill_id,
                    group_id=gid,
                    expected_minutes=entry.expected_minutes,
                    blurb=entry.blurb,
                )
            )
            member_node_ids[gid].append(node_id)

    # Step 6: budget, loudly - never silent pruning.
    if len(skill_nodes) > ceiling:
        raise MapGenerationError(
            ReasonCode.KNOWLEDGE_MAP_BUDGET_EXCEEDED,
            f"{template.pathway_id}: {len(skill_nodes)} skill nodes exceed the "
            f"ceiling of {ceiling}; trim seeds or split oversized groups",
        )

    # Step 3 continued: branch = the single seeding slot, or `core` for 2+.
    def branch_for(gid: str) -> str:
        slots = seeded_by[gid]
        return next(iter(slots)) if len(slots) == 1 else CORE_BRANCH

    groups = [
        KnowledgeGroup(
            group_id=gid,
            title=group_by_id[gid].title,
            branch=branch_for(gid),
            blurb=group_by_id[gid].blurb,
            member_node_ids=member_node_ids[gid],
        )
        for gid in included_group_ids
    ]

    # Step 4: one branch-level capstone per evidence slot.
    capstones = [
        KnowledgeNode(
            node_id="kn-" + slot.slot_id + "-capstone",
            title=slot.title,
            kind=KnowledgeNodeKind.CAPSTONE,
            evidence_slot_id=slot.slot_id,
            branch=slot.slot_id,
        )
        for slot in template.evidence_slots
    ]

    # Step 7: canonical ordering. Groups: `core` first, then slot order, then
    # group_id. Skill nodes: (group_id, skill_id). Capstones: slot order.
    def group_sort_key(group: KnowledgeGroup) -> tuple[int, int, str]:
        if group.branch == CORE_BRANCH:
            return (0, 0, group.group_id)
        return (1, slot_index.get(group.branch, len(slot_index)), group.group_id)

    groups.sort(key=group_sort_key)
    skill_nodes.sort(key=lambda n: (n.group_id or "", n.skill_id or ""))
    capstones.sort(key=lambda n: slot_index.get(n.evidence_slot_id or "", 0))

    return KnowledgeMap(groups=groups, nodes=[*skill_nodes, *capstones])
