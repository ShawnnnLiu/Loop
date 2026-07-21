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
* a **completion** (MM-B) adds ``minutes x confidence_weight(solve_confidence)``
  - the telemetry-minutes term; an absent self-report weighs ``1.0`` (opt-in, so
  not reporting is never punished);
* a **set-point** *rebases* the basis to
  ``tier_fraction[target] x honed_fraction x expected_minutes`` - later grants and
  completions accumulate on the new base; it is the only signal that can lower a
  node.

Events are folded in ``created_at`` order; on an exact tie the deterministic rank
is grant → completion → set-point, so a same-instant set-point still rebases last
(it always wins). The honed bar is ``honed_fraction x expected_minutes``.

Two bases fall out of the same fold (``apply_confidence_weight``): the **weighted**
basis drives the tier (:func:`map_state`), and a node is **review-flagged**
(:func:`mastery_memory`) when its **raw** basis meets the honed bar but its weighted
basis does not - the work happened, the confidence didn't. ``training`` is surfaced
via active-plan linkage. ``proven`` is computed for **capstones** (evidence-slot
filled) and, as of KT-C, for **skill nodes**: honed **and** carrying an
``evidence``-source grant (the mark-evidence anchor - user-gated, never automatic).
"""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime

from agentic_calendar.contracts.common_types import (
    KnowledgeNodeKind,
    MasteryGrantSource,
    MasteryTier,
)
from agentic_calendar.contracts.knowledge_map import KnowledgeMap, KnowledgeNode
from agentic_calendar.contracts.knowledge_map_overlay import (
    CustomNode,
    MasteryGrant,
    MasterySetPoint,
)
from agentic_calendar.contracts.telemetry import SolveConfidence


@dataclass(frozen=True)
class MasteryTuning:
    """Heuristic priors for the mastery ladder (axiom 07 threshold-change-log).

    Journaled through ``tuning.toml`` like every other prior; the kernel takes
    them as an argument so it never reads a file. ``discovered`` rebases to zero
    (a reset) and is not a tunable knob; ``proven`` is not settable, so a
    set-point to it rebases as ``honed``.

    The ``*_confidence_weight`` fields scale a completion's minutes by the user's
    ``solve_confidence`` self-report before it folds into the basis (MM-A priors;
    the weighting itself lands in MM-B). Absent confidence weighs ``1.0`` - the
    signal is opt-in and not reporting is never punished, so there is no
    ``absent`` knob to tune (``08-mastery-memory.md`` m1).
    """

    honed_fraction: float = 0.8
    setpoint_training_fraction: float = 0.5
    setpoint_honed_fraction: float = 1.0
    confident_confidence_weight: float = 1.0
    unsure_confidence_weight: float = 0.5
    needed_help_confidence_weight: float = 0.25


DEFAULT_MASTERY_TUNING = MasteryTuning()


@dataclass(frozen=True)
class NodeCompletion:
    """One completed task's contribution to a skill node's mastery basis (MM-B).

    ``minutes`` is the completion's attributed minutes (telemetry ``actual`` where
    recorded, planned otherwise - the composition root does that attribution).
    ``solve_confidence`` is the user's opt-in self-report; ``None`` means no triage
    and weighs ``1.0`` (never a penalty). The kernel applies the confidence weight
    from :class:`MasteryTuning` so the priors stay in one place.
    """

    minutes: int
    created_at: datetime
    solve_confidence: SolveConfidence | None = None


@dataclass(frozen=True)
class MasteryMemory:
    """The mastery aggregation the Strategist slice projects (MM-B / MM-C).

    ``mastered_node_ids`` are skill nodes at or above the honed bar on the
    *weighted* basis (mastered - stop assigning as primary study).
    ``review_node_ids`` are skill nodes whose *raw* minutes meet the bar but whose
    weighted basis does not (review-flagged - the work happened, the confidence
    didn't). The two sets are disjoint by construction (a node the confidence
    carries to honed is mastered, not review), matching the ``strategy-constraints``
    disjointness invariant. Capstones and personal custom nodes never appear here.
    """

    mastered_node_ids: frozenset[str]
    review_node_ids: frozenset[str]


def _confidence_weight(
    solve_confidence: SolveConfidence | None, tuning: MasteryTuning
) -> float:
    """The multiplier on a completion's minutes for its ``solve_confidence``.

    Absent (no triage) weighs ``1.0`` unconditionally - the signal is opt-in and
    not reporting is never punished, so there is no ``absent`` knob (m1).
    """
    if solve_confidence is None:
        return 1.0
    if solve_confidence is SolveConfidence.CONFIDENT:
        return tuning.confident_confidence_weight
    if solve_confidence is SolveConfidence.UNSURE:
        return tuning.unsure_confidence_weight
    return tuning.needed_help_confidence_weight


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
    *,
    completions: Sequence[NodeCompletion] = (),
    apply_confidence_weight: bool = True,
) -> float:
    """The mastery basis (minutes) for one skill node after the record fold.

    ``grants``, ``completions``, and ``setpoints`` are this node's records. The
    shared fold both ``map_state`` and :func:`mastery_memory` build on: grants and
    completions accumulate, the latest set-point (in ``created_at`` order) rebases,
    later grants and completions add on top. Deterministic tie-break on an exact
    timestamp: grant → completion → set-point.

    ``apply_confidence_weight`` scales each completion by its ``solve_confidence``
    (the *weighted* basis, driving the tier). Pass ``False`` for the *raw* basis -
    the review-flag comparison in :func:`mastery_memory` counts full minutes.
    """
    events: list[tuple[MasteryGrant | NodeCompletion | MasterySetPoint, int]] = (
        [(g, 0) for g in grants]
        + [(c, 1) for c in completions]
        + [(s, 2) for s in setpoints]
    )
    events.sort(key=lambda item: (item[0].created_at, item[1]))
    basis = 0.0
    for record, _rank in events:
        if isinstance(record, MasteryGrant):
            basis += record.credit_minutes
        elif isinstance(record, NodeCompletion):
            weight = (
                _confidence_weight(record.solve_confidence, tuning)
                if apply_confidence_weight
                else 1.0
            )
            basis += record.minutes * weight
        else:
            basis = _setpoint_fraction(record.target_tier, tuning) * (
                tuning.honed_fraction * expected_minutes
            )
    return basis


def _skill_tier(
    node: KnowledgeNode,
    grants: Sequence[MasteryGrant],
    setpoints: Sequence[MasterySetPoint],
    completions: Sequence[NodeCompletion],
    *,
    in_training: bool,
    tuning: MasteryTuning,
) -> MasteryTier:
    expected = node.expected_minutes or 0
    basis = folded_basis(expected, grants, setpoints, tuning, completions=completions)
    honed_bar = tuning.honed_fraction * expected
    if expected > 0 and basis >= honed_bar:
        # A skill node is `proven` when it is honed AND a confirmed evidence item
        # carries a matching anchor - modeled (KT-C) as an ``evidence``-source
        # grant on the node (``06-…`` tiers; user-gated via "mark evidence",
        # never automatic).
        if any(g.source is MasteryGrantSource.EVIDENCE for g in grants):
            return MasteryTier.PROVEN
        return MasteryTier.HONED
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


def _group_by_node(
    grants: Sequence[MasteryGrant], setpoints: Sequence[MasterySetPoint]
) -> tuple[dict[str, list[MasteryGrant]], dict[str, list[MasterySetPoint]]]:
    grants_by_node: dict[str, list[MasteryGrant]] = {}
    for grant in grants:
        grants_by_node.setdefault(grant.node_id, []).append(grant)
    setpoints_by_node: dict[str, list[MasterySetPoint]] = {}
    for setpoint in setpoints:
        setpoints_by_node.setdefault(setpoint.node_id, []).append(setpoint)
    return grants_by_node, setpoints_by_node


def map_state(
    knowledge_map: KnowledgeMap,
    *,
    grants: Sequence[MasteryGrant] = (),
    setpoints: Sequence[MasterySetPoint] = (),
    completions: Mapping[str, Sequence[NodeCompletion]] | None = None,
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
    and ``in_progress_slot_ids`` come from slot coverage / story progress;
    ``completions`` maps a skill node to its completed-task contributions (MM-B) -
    the confidence-weighted telemetry term folded into the tier.
    """
    completions = completions or {}
    training = set(training_node_ids)
    grants_by_node, setpoints_by_node = _group_by_node(grants, setpoints)

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
                completions.get(node.node_id, ()),
                in_training=node.node_id in training,
                tuning=tuning,
            )

    # Personal custom nodes: set-points are their only mastery source; they cap
    # at honed and count toward nothing (06-… content classes).
    for custom in custom_nodes:
        tier = _latest_setpoint_tier(setpoints_by_node.get(custom.custom_node_id, []))
        tiers[custom.custom_node_id] = tier or MasteryTier.DISCOVERED

    return tiers


def mastery_memory(
    knowledge_map: KnowledgeMap,
    *,
    grants: Sequence[MasteryGrant] = (),
    setpoints: Sequence[MasterySetPoint] = (),
    completions: Mapping[str, Sequence[NodeCompletion]] | None = None,
    tuning: MasteryTuning = DEFAULT_MASTERY_TUNING,
) -> MasteryMemory:
    """Fold the account's records into mastered / review-flagged skill-node sets.

    The Strategist-slice aggregation (``08-mastery-memory.md``), built on the same
    :func:`folded_basis` as :func:`map_state`. Only **skill** nodes participate -
    capstones are evidence-pillars, not study targets, and custom nodes are
    display-only. A node is **mastered** when its confidence-weighted basis meets
    the honed bar; **review-flagged** when its raw minutes meet the bar but the
    weighted basis does not (disjoint by the ``elif``). MM-C projects these onto
    the account map ids for the ``StrategyConstraints`` mastery slice.
    """
    completions = completions or {}
    grants_by_node, setpoints_by_node = _group_by_node(grants, setpoints)

    mastered: set[str] = set()
    review: set[str] = set()
    for node in knowledge_map.nodes:
        if node.kind is KnowledgeNodeKind.CAPSTONE:
            continue
        expected = node.expected_minutes or 0
        if expected <= 0:
            continue
        node_grants = grants_by_node.get(node.node_id, [])
        node_setpoints = setpoints_by_node.get(node.node_id, [])
        node_completions = completions.get(node.node_id, ())
        honed_bar = tuning.honed_fraction * expected
        weighted = folded_basis(
            expected, node_grants, node_setpoints, tuning, completions=node_completions
        )
        if weighted >= honed_bar:
            mastered.add(node.node_id)
            continue
        raw = folded_basis(
            expected,
            node_grants,
            node_setpoints,
            tuning,
            completions=node_completions,
            apply_confidence_weight=False,
        )
        if raw >= honed_bar:
            review.add(node.node_id)
    return MasteryMemory(frozenset(mastered), frozenset(review))
