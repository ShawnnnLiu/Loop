"""``knowledge_map`` contract (KT-A).

Canonical spec: ``docs/specs/pathway-template.schema.md`` (Knowledge Map
section).

A :class:`KnowledgeMap` is the two-level grouped map for one pathway: branches
(one per evidence slot) hold **group** waypoints that expand into their member
**skill** nodes, plus one branch-level **capstone** per evidence slot. It is
*emitted by the deterministic generator* (``07-tree-generation.md``, KT-B),
never hand-authored, and attached to its :class:`PathwayTemplate` at registry
import.

This module defines only the *shape* and internal consistency (unique ids,
both-way group membership, capstone-per-slot, kind-conditional fields). There
are **no edges** - membership is a function, so cycle handling does not exist.
Registry-level checks (``skill_id`` resolution against the pinned taxonomy,
``evidence_slot_id`` membership in the template, the prestige denylist) live in
the generator/registry tests (KT-B), not here.

The map is a presentation and memory layer: it never gates the Planner, the
Scheduler, or task availability (axiom 11 non-interference rule).
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from ._dedup import find_duplicates
from .common_types import KnowledgeNodeKind

GroupId = Annotated[str, StringConstraints(pattern=r"^kg-[a-z0-9-]+$")]
NodeId = Annotated[str, StringConstraints(pattern=r"^kn-[a-z0-9-]+$")]


class KnowledgeGroup(BaseModel):
    """A group waypoint: a clickable cluster of member skill nodes."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    group_id: GroupId
    title: str = Field(min_length=1)
    branch: str = Field(min_length=1)
    """The evidence ``slot_id`` the group serves, or ``core`` (2+ slots)."""
    blurb: str = Field(min_length=1)
    member_node_ids: list[NodeId] = Field(min_length=1)

    @model_validator(mode="after")
    def _member_node_ids_unique(self) -> KnowledgeGroup:
        dupes = find_duplicates(self.member_node_ids)
        if dupes:
            raise ValueError(f"member_node_ids must be unique; duplicates: {dupes}")
        return self


class KnowledgeNode(BaseModel):
    """One map node: a taxonomy-anchored ``skill`` or a branch-level ``capstone``.

    Kind-conditional fields (enforced below):

    * ``skill`` requires ``skill_id``, ``group_id``, ``expected_minutes`` and
      forbids ``evidence_slot_id`` / ``branch``.
    * ``capstone`` requires ``evidence_slot_id``, ``branch`` and forbids
      ``skill_id`` / ``group_id`` / ``expected_minutes``.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    node_id: NodeId
    title: str = Field(min_length=1)
    kind: KnowledgeNodeKind
    skill_id: str | None = Field(default=None, min_length=1)
    group_id: GroupId | None = None
    expected_minutes: int | None = Field(default=None, gt=0)
    evidence_slot_id: str | None = Field(default=None, min_length=1)
    branch: str | None = Field(default=None, min_length=1)
    blurb: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def _kind_conditional_fields(self) -> KnowledgeNode:
        if self.kind is KnowledgeNodeKind.SKILL:
            missing = [
                name
                for name, value in (
                    ("skill_id", self.skill_id),
                    ("group_id", self.group_id),
                    ("expected_minutes", self.expected_minutes),
                )
                if value is None
            ]
            if missing:
                raise ValueError(
                    f"skill node {self.node_id!r} requires {missing}"
                )
            forbidden = [
                name
                for name, value in (
                    ("evidence_slot_id", self.evidence_slot_id),
                    ("branch", self.branch),
                )
                if value is not None
            ]
            if forbidden:
                raise ValueError(
                    f"skill node {self.node_id!r} forbids {forbidden}"
                )
        else:  # capstone
            missing = [
                name
                for name, value in (
                    ("evidence_slot_id", self.evidence_slot_id),
                    ("branch", self.branch),
                )
                if value is None
            ]
            if missing:
                raise ValueError(
                    f"capstone node {self.node_id!r} requires {missing}"
                )
            forbidden = [
                name
                for name, value in (
                    ("skill_id", self.skill_id),
                    ("group_id", self.group_id),
                    ("expected_minutes", self.expected_minutes),
                )
                if value is not None
            ]
            if forbidden:
                raise ValueError(
                    f"capstone node {self.node_id!r} forbids {forbidden}"
                )
        return self


class KnowledgeMap(BaseModel):
    """A pathway's generated grouped map: groups + nodes, no edges."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    groups: list[KnowledgeGroup] = Field(min_length=1)
    nodes: list[KnowledgeNode] = Field(min_length=1)

    @model_validator(mode="after")
    def _ids_unique(self) -> KnowledgeMap:
        group_dupes = find_duplicates([g.group_id for g in self.groups])
        if group_dupes:
            raise ValueError(f"group_id values must be unique; duplicates: {group_dupes}")
        node_dupes = find_duplicates([n.node_id for n in self.nodes])
        if node_dupes:
            raise ValueError(f"node_id values must be unique; duplicates: {node_dupes}")
        return self

    @model_validator(mode="after")
    def _group_membership_resolves_both_ways(self) -> KnowledgeMap:
        groups_by_id = {g.group_id: g for g in self.groups}
        skill_nodes = {
            n.node_id: n for n in self.nodes if n.kind is KnowledgeNodeKind.SKILL
        }
        # Every skill node's group exists and lists it.
        for node in skill_nodes.values():
            group = groups_by_id.get(node.group_id or "")
            if group is None:
                raise ValueError(
                    f"skill node {node.node_id!r} names unknown group {node.group_id!r}"
                )
            if node.node_id not in group.member_node_ids:
                raise ValueError(
                    f"skill node {node.node_id!r} not listed in its group "
                    f"{group.group_id!r} member_node_ids"
                )
        # Every membership entry resolves to a skill node pointing back here.
        for group in self.groups:
            for member_id in group.member_node_ids:
                member = skill_nodes.get(member_id)
                if member is None:
                    raise ValueError(
                        f"group {group.group_id!r} lists member {member_id!r} "
                        "that is not a skill node in this map"
                    )
                if member.group_id != group.group_id:
                    raise ValueError(
                        f"group {group.group_id!r} lists member {member_id!r} "
                        f"whose group_id is {member.group_id!r}"
                    )
        return self

    @model_validator(mode="after")
    def _one_capstone_per_slot(self) -> KnowledgeMap:
        slots: list[str] = [
            n.evidence_slot_id or ""
            for n in self.nodes
            if n.kind is KnowledgeNodeKind.CAPSTONE
        ]
        dupes = find_duplicates(slots)
        if dupes:
            raise ValueError(
                f"at most one capstone per evidence slot; duplicated slots: {dupes}"
            )
        return self
