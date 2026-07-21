"""Deterministic mastery tiers - the ``map_state`` fold (narrative-pathways KT-B).

``map_state`` folds an account's overlay records over a generated
:class:`KnowledgeMap` into a per-node :class:`MasteryTier` - the four-state
deterministic ladder of ``06-knowledge-tree.md``. No LLM assigns, names, or
explains a tier (axiom 00); the tier is a pure function of stored records and
the account's active-plan / evidence signals, all passed in as plain data so
this stays a leaf kernel (``contracts`` + ``common`` only) and free text can
never reach it.

The basis fold (``08-mastery-memory.md``), for a taxonomy-anchored skill node:

* **grants** add ``credit_minutes`` to the basis;
* a **set-point** *rebases* the basis to
  ``tier_fraction[target] x honed_fraction x expected_minutes`` - later grants
  accumulate on the new base; it is the only signal that can lower a node.

Events are folded in ``created_at`` order (grants before set-points on an exact
tie - a total, deterministic order). The honed bar is
``honed_fraction x expected_minutes``.

Scope (KT-B): the fold covers **grants + set-points**; the *telemetry-minutes*
term and its ``solve_confidence`` weighting are added in MM-B onto this same
``folded_basis`` implementation. ``training`` is still surfaced here via active-
plan linkage. ``proven`` is computed for **capstones** (evidence-slot filled);
skill-node ``proven`` (a confirmed evidence anchor) lands with the mark-evidence
wiring in KT-C, so skill nodes cap at ``honed`` here.
"""

from __future__ import annotations

from collections.abc import Collection, Sequence
from dataclasses import dataclass

from agentic_calendar.contracts.common_types import KnowledgeNodeKind, MasteryTier
from agentic_calendar.contracts.knowledge_map import KnowledgeMap, KnowledgeNode
from agentic_calendar.contracts.knowledge_map_overlay import (
    CustomNode,
    MasteryGrant,
    MasterySetPoint,
)


@dataclass(frozen=True)
class MasteryTuning:
    """Heuristic priors for the mastery ladder (axiom 07 threshold-change-log).

    Journaled through ``tuning.toml`` like every other prior; the kernel takes
    them as an argument so it never reads a file. ``discovered`` rebases to zero
    (a reset) and is not a tunable knob; ``proven`` is not settable, so a
    set-point to it rebases as ``honed``.
    """

    honed_fraction: float = 0.8
    setpoint_training_fraction: float = 0.5
    setpoint_honed_fraction: float = 1.0


DEFAULT_MASTERY_TUNING = MasteryTuning()


def _setpoint_fraction(tier: MasteryTier, tuning: MasteryTuning) -> float:
    if tier is MasteryTier.DISCOVERED:
        return 0.0
    if tier is MasteryTier.TRAINING:
        return tuning.setpoint_training_fraction
    # honed, and proven (not settable) -> treated as honed; proven stays
    # evidence-gated and is never reached through a set-point.
    return tuning.setpoint_honed_fraction


def folded_basis(
    expected_minutes: int,
    grants: Sequence[MasteryGrant],
    setpoints: Sequence[MasterySetPoint],
    tuning: MasteryTuning = DEFAULT_MASTERY_TUNING,
) -> float:
    """The mastery basis (minutes) for one skill node after the record fold.

    ``grants`` and ``setpoints`` are this node's records. The shared fold both
    ``map_state`` and the MM mastery aggregation build on: grants accumulate,
    the latest set-point (in ``created_at`` order) rebases, later grants add on
    top. Deterministic tie-break: a grant folds before a set-point sharing a
    timestamp.
    """
    events: list[tuple[MasteryGrant | MasterySetPoint, int]] = [
        (g, 0) for g in grants
    ] + [(s, 1) for s in setpoints]
    events.sort(key=lambda item: (item[0].created_at, item[1]))
    basis = 0.0
    for record, _rank in events:
        if isinstance(record, MasteryGrant):
            basis += record.credit_minutes
        else:
            basis = _setpoint_fraction(record.target_tier, tuning) * (
                tuning.honed_fraction * expected_minutes
            )
    return basis


def _skill_tier(
    node: KnowledgeNode,
    grants: Sequence[MasteryGrant],
    setpoints: Sequence[MasterySetPoint],
    *,
    in_training: bool,
    tuning: MasteryTuning,
) -> MasteryTier:
    expected = node.expected_minutes or 0
    basis = folded_basis(expected, grants, setpoints, tuning)
    honed_bar = tuning.honed_fraction * expected
    if expected > 0 and basis >= honed_bar:
        return MasteryTier.HONED  # skill `proven` is evidence-gated (KT-C)
    if basis > 0 or in_training:
        return MasteryTier.TRAINING
    return MasteryTier.DISCOVERED


def _capstone_tier(
    node: KnowledgeNode,
    *,
    filled_slot_ids: Collection[str],
    in_progress_slot_ids: Collection[str],
) -> MasteryTier:
    slot = node.evidence_slot_id
    if slot in filled_slot_ids:
        return MasteryTier.PROVEN  # user-gated: the slot is filled by confirmed evidence
    if slot in in_progress_slot_ids:
        return MasteryTier.TRAINING
    return MasteryTier.DISCOVERED


def _latest_setpoint_tier(setpoints: Sequence[MasterySetPoint]) -> MasteryTier | None:
    if not setpoints:
        return None
    latest = max(setpoints, key=lambda s: s.created_at)
    # Custom nodes cap at honed - proven needs an evidence anchor they lack.
    if latest.target_tier is MasteryTier.PROVEN:
        return MasteryTier.HONED
    return latest.target_tier


def map_state(
    knowledge_map: KnowledgeMap,
    *,
    grants: Sequence[MasteryGrant] = (),
    setpoints: Sequence[MasterySetPoint] = (),
    custom_nodes: Sequence[CustomNode] = (),
    training_node_ids: Collection[str] = (),
    filled_slot_ids: Collection[str] = (),
    in_progress_slot_ids: Collection[str] = (),
    tuning: MasteryTuning = DEFAULT_MASTERY_TUNING,
) -> dict[str, MasteryTier]:
    """Per-node :class:`MasteryTier` for the account's ``knowledge_map``.

    Returns a tier for every skill and capstone node in the map, plus every
    ``custom_nodes`` node (personal layer). ``training_node_ids`` are skill
    nodes with at least one linked task in the active plan; ``filled_slot_ids``
    and ``in_progress_slot_ids`` come from slot coverage / story progress.
    """
    training = set(training_node_ids)
    grants_by_node: dict[str, list[MasteryGrant]] = {}
    for grant in grants:
        grants_by_node.setdefault(grant.node_id, []).append(grant)
    setpoints_by_node: dict[str, list[MasterySetPoint]] = {}
    for setpoint in setpoints:
        setpoints_by_node.setdefault(setpoint.node_id, []).append(setpoint)

    tiers: dict[str, MasteryTier] = {}
    for node in knowledge_map.nodes:
        if node.kind is KnowledgeNodeKind.CAPSTONE:
            tiers[node.node_id] = _capstone_tier(
                node,
                filled_slot_ids=filled_slot_ids,
                in_progress_slot_ids=in_progress_slot_ids,
            )
        else:
            tiers[node.node_id] = _skill_tier(
                node,
                grants_by_node.get(node.node_id, []),
                setpoints_by_node.get(node.node_id, []),
                in_training=node.node_id in training,
                tuning=tuning,
            )

    # Personal custom nodes: set-points are their only mastery source; they cap
    # at honed and count toward nothing (06-… content classes).
    for custom in custom_nodes:
        tier = _latest_setpoint_tier(setpoints_by_node.get(custom.custom_node_id, []))
        tiers[custom.custom_node_id] = tier or MasteryTier.DISCOVERED

    return tiers
