"""The account's pathway-content knowledge nodes (narrative-pathways KT-C).

An account's knowledge map is the generated :class:`KnowledgeMap` of its
selected pathway **plus** the append-only overlay of taxonomy-anchored
:class:`NodeAddition`s (``06-knowledge-tree.md`` content classes). The Strategist
tags modules against the *skill* nodes of that pathway content (capstones are
evidence-gated, never training targets), and the deterministic gate rejects any
tag outside it (``UNKNOWN_KNOWLEDGE_NODE``).

:func:`pathway_node_vocabulary` is the pure projection both use: it produces the
ordered ``(node_id, title)`` vocabulary the composition root puts on
``StrategyConstraints.knowledge_nodes`` and the same set the gate checks against,
so prompt and gate can never drift. Personal custom content never enters here -
that is the injection wall, stated once in ``06-…``.

Leaf kernel: depends only on ``contracts`` and this package's ``generation``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from agentic_calendar.contracts.common_types import KnowledgeNodeKind
from agentic_calendar.contracts.knowledge_map import KnowledgeMap
from agentic_calendar.contracts.knowledge_map_overlay import NodeAddition
from agentic_calendar.contracts.skill_grouping import SkillGrouping
from agentic_calendar.contracts.skill_taxonomy import SkillTaxonomy

from .generation import CORE_BRANCH, node_id_for


def pathway_node_vocabulary(
    generated_map: KnowledgeMap,
    *,
    additions: Sequence[NodeAddition] = (),
    display_names: Mapping[str, str],
) -> list[tuple[str, str]]:
    """Ordered ``(node_id, title)`` vocabulary of the account's pathway content.

    The generated map's skill nodes in their committed canonical order, then each
    taxonomy-anchored ``NodeAddition`` not already present, sorted by ``node_id``
    (a total, deterministic order so the projected list is byte-stable). ``title``
    comes from the map for generated nodes and from ``display_names`` (the pinned
    taxonomy display name) for additions; an addition whose skill has no display
    name is skipped defensively (the add-node API rejects such a skill at write
    time). Capstones are excluded - they are not training targets.
    """
    vocab: list[tuple[str, str]] = [
        (node.node_id, node.title)
        for node in generated_map.nodes
        if node.kind is KnowledgeNodeKind.SKILL
    ]
    present = {node_id for node_id, _title in vocab}

    extra: list[tuple[str, str]] = []
    for addition in additions:
        node_id = node_id_for(addition.skill_id)
        if node_id in present:
            continue
        title = display_names.get(addition.skill_id)
        if title is None:
            continue
        present.add(node_id)
        extra.append((node_id, title))

    extra.sort(key=lambda item: item[0])
    return [*vocab, *extra]


def merge_additions(
    generated_map: KnowledgeMap,
    additions: Sequence[NodeAddition],
    *,
    grouping: SkillGrouping,
    taxonomy: SkillTaxonomy,
) -> KnowledgeMap:
    """The account's map: the generated map with taxonomy-anchored additions placed.

    Each :class:`NodeAddition` lands in the group its ``skill-grouping`` row names
    (``06-…``: the user picks *what*, code decides *where*); if that group is not
    yet on the map it is added with the one member (branch ``core`` - an addition
    serves no pathway slot on this account). An addition whose skill is already a
    node, or has no grouping row / taxonomy display name, is skipped defensively -
    the add-node API (KT-C) rejects those at write time. The result is re-validated
    against the :class:`KnowledgeMap` contract, so it satisfies every invariant
    (unique ids, both-way membership) or raises.

    Personal custom groups/nodes are **not** merged here - they carry ``kcg-`` /
    ``kcn-`` ids the ``KnowledgeMap`` contract forbids and count toward nothing
    (``06-…`` content classes); the service renders them as a separate layer.
    """
    display = {e.skill_id: e.display_name for e in taxonomy.entries}
    entry_by_skill = {e.skill_id: e for e in grouping.entries}
    group_by_id = {g.group_id: g for g in grouping.groups}

    groups: dict[str, dict[str, Any]] = {
        g.group_id: g.model_dump() for g in generated_map.groups
    }
    nodes: list[dict[str, Any]] = [n.model_dump() for n in generated_map.nodes]
    present = {n["node_id"] for n in nodes}

    for addition in additions:
        node_id = node_id_for(addition.skill_id)
        if node_id in present:
            continue
        entry = entry_by_skill.get(addition.skill_id)
        title = display.get(addition.skill_id)
        if entry is None or title is None:
            continue
        group = group_by_id.get(entry.group_id)
        if group is None:
            continue
        if entry.group_id not in groups:
            groups[entry.group_id] = {
                "group_id": group.group_id,
                "title": group.title,
                "branch": CORE_BRANCH,
                "blurb": group.blurb,
                "member_node_ids": [],
            }
        nodes.append(
            {
                "node_id": node_id,
                "title": title,
                "kind": KnowledgeNodeKind.SKILL.value,
                "skill_id": addition.skill_id,
                "group_id": entry.group_id,
                "expected_minutes": entry.expected_minutes,
                "blurb": entry.blurb,
            }
        )
        groups[entry.group_id]["member_node_ids"].append(node_id)
        present.add(node_id)

    return KnowledgeMap.model_validate(
        {"groups": list(groups.values()), "nodes": nodes}
    )
