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

from agentic_calendar.contracts.common_types import KnowledgeNodeKind
from agentic_calendar.contracts.knowledge_map import KnowledgeMap
from agentic_calendar.contracts.knowledge_map_overlay import NodeAddition

from .generation import node_id_for


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
