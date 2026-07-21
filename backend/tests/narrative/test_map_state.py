"""Exhaustive mastery-tier tests for the ``map_state`` fold (KT-B).

Covers every transition, fold ordering, set-point rebase, grant accumulation,
the add-only property, capstone evidence-gating, and custom-node caps. Tiers are
a pure function of stored records + active-plan / coverage signals; nothing here
touches an LLM or reads a file.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from agentic_calendar.contracts.common_types import (
    KnowledgeNodeKind,
    MasteryGrantSource,
    MasteryTier,
)
from agentic_calendar.contracts.knowledge_map import (
    KnowledgeGroup,
    KnowledgeMap,
    KnowledgeNode,
)
from agentic_calendar.contracts.knowledge_map_overlay import (
    CustomNode,
    MasteryGrant,
    MasterySetPoint,
)
from agentic_calendar.narrative import map_state
from agentic_calendar.narrative.generation import generate_map
from agentic_calendar.narrative.mastery import DEFAULT_MASTERY_TUNING, folded_basis
from agentic_calendar.skill_taxonomy import load_skill_grouping, load_taxonomy
from agentic_calendar.templates import list_pathways

_T0 = datetime(2026, 7, 20, 12, 0, tzinfo=UTC)
_EXPECTED = 100  # honed bar = 0.8 * 100 = 80 minutes


def _at(minutes: int) -> datetime:
    return _T0 + timedelta(minutes=minutes)


def _map(expected: int = _EXPECTED) -> KnowledgeMap:
    return KnowledgeMap(
        groups=[
            KnowledgeGroup(
                group_id="kg-x",
                title="X",
                branch="s",
                blurb="b",
                member_node_ids=["kn-a"],
            )
        ],
        nodes=[
            KnowledgeNode(
                node_id="kn-a",
                title="A",
                kind=KnowledgeNodeKind.SKILL,
                skill_id="skill.a",
                group_id="kg-x",
                expected_minutes=expected,
                blurb="b",
            ),
            KnowledgeNode(
                node_id="kn-s-capstone",
                title="Cap",
                kind=KnowledgeNodeKind.CAPSTONE,
                evidence_slot_id="s",
                branch="s",
            ),
        ],
    )


def _grant(minutes: int, at: datetime) -> MasteryGrant:
    return MasteryGrant(
        user_id="u1",
        node_id="kn-a",
        credit_minutes=minutes,
        source=MasteryGrantSource.ONBOARDING,
        created_at=at,
    )


def _setpoint(tier: MasteryTier, at: datetime, node_id: str = "kn-a") -> MasterySetPoint:
    return MasterySetPoint(user_id="u1", node_id=node_id, target_tier=tier, created_at=at)


def _skill(**kwargs: object) -> MasteryTier:
    return map_state(_map(), **kwargs)["kn-a"]  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# Skill-node tiers.
# --------------------------------------------------------------------------- #


def test_no_records_no_plan_is_discovered() -> None:
    assert _skill() is MasteryTier.DISCOVERED


def test_linked_active_plan_task_is_training() -> None:
    assert _skill(training_node_ids={"kn-a"}) is MasteryTier.TRAINING


def test_partial_grant_below_bar_is_training() -> None:
    assert _skill(grants=[_grant(40, _at(1))]) is MasteryTier.TRAINING


def test_grant_at_or_over_bar_is_honed() -> None:
    assert _skill(grants=[_grant(80, _at(1))]) is MasteryTier.HONED
    assert _skill(grants=[_grant(120, _at(1))]) is MasteryTier.HONED


def _evidence_grant(minutes: int, at: datetime) -> MasteryGrant:
    return MasteryGrant(
        user_id="u1",
        node_id="kn-a",
        credit_minutes=minutes,
        source=MasteryGrantSource.EVIDENCE,
        created_at=at,
    )


def test_evidence_grant_at_the_bar_is_proven() -> None:
    # honed AND an evidence-source grant (the mark-evidence anchor) -> proven.
    assert _skill(grants=[_evidence_grant(80, _at(1))]) is MasteryTier.PROVEN


def test_evidence_grant_below_the_bar_is_only_training() -> None:
    # proven requires honed first; an evidence grant that doesn't reach the bar
    # does not shortcut it.
    assert _skill(grants=[_evidence_grant(40, _at(1))]) is MasteryTier.TRAINING


def test_honed_by_setpoint_plus_evidence_grant_is_proven() -> None:
    # honed can come from a set-point; the evidence grant on top marks it proven.
    assert (
        _skill(
            setpoints=[_setpoint(MasteryTier.HONED, _at(1))],
            grants=[_evidence_grant(1, _at(2))],
        )
        is MasteryTier.PROVEN
    )


def test_grants_accumulate() -> None:
    grants = [_grant(40, _at(1)), _grant(40, _at(2))]
    assert _skill(grants=grants) is MasteryTier.HONED  # 40 + 40 = 80 = bar


def test_setpoint_honed_reaches_the_bar() -> None:
    assert _skill(setpoints=[_setpoint(MasteryTier.HONED, _at(1))]) is MasteryTier.HONED


def test_setpoint_training_is_below_the_bar() -> None:
    # 0.5 * 0.8 * 100 = 40 < 80
    assert _skill(setpoints=[_setpoint(MasteryTier.TRAINING, _at(1))]) is MasteryTier.TRAINING


def test_setpoint_down_rebases_and_lowers() -> None:
    # A grant reaches honed, then an explicit set-point to discovered resets it.
    records_grants = [_grant(120, _at(1))]
    setpoints = [_setpoint(MasteryTier.DISCOVERED, _at(2))]
    assert _skill(grants=records_grants, setpoints=setpoints) is MasteryTier.DISCOVERED


def test_grant_after_setpoint_accumulates_on_the_new_base() -> None:
    # set-point to discovered (basis 0 at t2), then a 90-min grant at t3 -> honed.
    grants = [_grant(90, _at(3))]
    setpoints = [_setpoint(MasteryTier.DISCOVERED, _at(2))]
    assert _skill(grants=grants, setpoints=setpoints) is MasteryTier.HONED


def test_fold_order_is_by_created_at_not_argument_order() -> None:
    # grant(120)@t1 then setpoint(discovered)@t2 -> reset -> discovered.
    reset_after = _skill(
        grants=[_grant(120, _at(1))], setpoints=[_setpoint(MasteryTier.DISCOVERED, _at(2))]
    )
    # setpoint(discovered)@t1 then grant(120)@t2 -> accumulates -> honed.
    grant_after = _skill(
        grants=[_grant(120, _at(2))], setpoints=[_setpoint(MasteryTier.DISCOVERED, _at(1))]
    )
    assert reset_after is MasteryTier.DISCOVERED
    assert grant_after is MasteryTier.HONED


def test_add_only_property_grants_never_lower() -> None:
    # Starting honed, an additional grant can never drop the tier.
    base = [_grant(80, _at(1))]
    more = [*base, _grant(30, _at(2))]
    assert _skill(grants=base) is MasteryTier.HONED
    assert _skill(grants=more) is MasteryTier.HONED


def test_skill_never_reaches_proven_in_kt_b() -> None:
    # Even a set-point to proven caps at honed (skill proven is evidence-gated).
    assert _skill(setpoints=[_setpoint(MasteryTier.PROVEN, _at(1))]) is MasteryTier.HONED


# --------------------------------------------------------------------------- #
# Capstone tiers (evidence-gated).
# --------------------------------------------------------------------------- #


def test_capstone_proven_when_slot_filled() -> None:
    tiers = map_state(_map(), filled_slot_ids={"s"})
    assert tiers["kn-s-capstone"] is MasteryTier.PROVEN


def test_capstone_training_when_slot_in_progress() -> None:
    tiers = map_state(_map(), in_progress_slot_ids={"s"})
    assert tiers["kn-s-capstone"] is MasteryTier.TRAINING


def test_capstone_discovered_by_default() -> None:
    assert map_state(_map())["kn-s-capstone"] is MasteryTier.DISCOVERED


def test_filled_slot_wins_over_in_progress() -> None:
    tiers = map_state(_map(), filled_slot_ids={"s"}, in_progress_slot_ids={"s"})
    assert tiers["kn-s-capstone"] is MasteryTier.PROVEN


# --------------------------------------------------------------------------- #
# Custom nodes (personal layer; set-points only, cap at honed).
# --------------------------------------------------------------------------- #


def _custom() -> CustomNode:
    return CustomNode(
        user_id="u1",
        custom_node_id="kcn-mine",
        name="Mine",
        group_id="kcg-mine",
        created_at=_T0,
    )


def test_custom_node_defaults_to_discovered() -> None:
    tiers = map_state(_map(), custom_nodes=[_custom()])
    assert tiers["kcn-mine"] is MasteryTier.DISCOVERED


def test_custom_node_takes_its_latest_setpoint() -> None:
    setpoints = [
        _setpoint(MasteryTier.TRAINING, _at(1), node_id="kcn-mine"),
        _setpoint(MasteryTier.HONED, _at(2), node_id="kcn-mine"),
    ]
    tiers = map_state(_map(), custom_nodes=[_custom()], setpoints=setpoints)
    assert tiers["kcn-mine"] is MasteryTier.HONED


def test_custom_node_caps_at_honed() -> None:
    setpoints = [_setpoint(MasteryTier.PROVEN, _at(1), node_id="kcn-mine")]
    tiers = map_state(_map(), custom_nodes=[_custom()], setpoints=setpoints)
    assert tiers["kcn-mine"] is MasteryTier.HONED


# --------------------------------------------------------------------------- #
# Fold helper + completeness over a real map.
# --------------------------------------------------------------------------- #


def test_folded_basis_matches_the_hand_computed_value() -> None:
    basis = folded_basis(
        _EXPECTED,
        [_grant(40, _at(1)), _grant(25, _at(2))],
        [],
        DEFAULT_MASTERY_TUNING,
    )
    assert basis == 65.0


def test_every_node_of_a_real_map_gets_a_tier() -> None:
    taxonomy = load_taxonomy()
    grouping = load_skill_grouping()
    for pathway in list_pathways():
        kmap = generate_map(pathway, grouping, taxonomy)
        tiers = map_state(kmap)
        assert set(tiers) == {n.node_id for n in kmap.nodes}
        assert all(t is MasteryTier.DISCOVERED for t in tiers.values())
