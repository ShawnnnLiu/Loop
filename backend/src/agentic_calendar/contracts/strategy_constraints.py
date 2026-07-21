"""``strategy_constraints`` contract.

Canonical spec: ``docs/specs/strategy-constraints.schema.md`` (referenced by
``docs/specs/syllabus-units.schema.md`` "Strategist Inputs").

The deterministic bounds the Strategist must respect when proposing a syllabus.
The Strategist *proposes* modules; these constraints are part of what the
deterministic layer uses to *dispose* (gate / repair) its output.

The pathway fields (narrative-pathways NP-A) are filled by the composition
root from the profile's confirmed ``pathway_selection`` (NP-D): the
``narrative/`` kernel computes ``unfilled_slots`` deterministically and the
Strategist is *told* the gaps, never asked to find them. Defaults keep ``{}``
valid, so a profile without a selection produces today's bundle unchanged.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

from ._dedup import find_duplicates
from .common_types import Priority

#: A generated (taxonomy-anchored) knowledge-map node id (``kn-…``). Capstones
#: are not training targets, so the vocabulary carries skill nodes only.
KnowledgeNodeId = Annotated[str, StringConstraints(pattern=r"^kn-[a-z0-9-]+$")]


def _default_priority_values() -> list[Priority]:
    return [Priority.HIGH, Priority.MEDIUM, Priority.LOW]


class KnowledgeNodeRef(BaseModel):
    """One trainable skill node on the account's knowledge map (KT-C).

    The closed vocabulary the Strategist may tag modules against: ``node_id``
    plus the taxonomy ``title`` (a curated display name, never user free text).
    The account's *pathway content* only - generated skill nodes plus
    taxonomy-anchored additions; personal custom content never appears here (the
    injection wall, ``06-knowledge-tree.md``).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    node_id: KnowledgeNodeId
    title: str = Field(min_length=1)


class UnfilledSlot(BaseModel):
    """One unfilled evidence slot, projected from the selected pathway.

    A display/seed projection of ``EvidenceSlot`` (pathway-template spec):
    ``gap_module_hint`` seeds module wording and is never control flow.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    slot_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    gap_module_hint: str = Field(min_length=1)


class StrategyConstraints(BaseModel):
    """Bounds on a Strategist proposal (spec defaults shown)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    max_modules: int = Field(default=12, gt=0, le=100)
    required_priority_values: list[Priority] = Field(
        default_factory=_default_priority_values
    )
    max_total_estimated_minutes: int = Field(default=4800, gt=0)
    must_reference_claims_for_company_specific_modules: bool = True
    pathway_id: str | None = Field(default=None, min_length=1)
    unfilled_slots: list[UnfilledSlot] = Field(default_factory=list)
    max_slot_modules: int = Field(default=3, gt=0, le=10)
    knowledge_nodes: list[KnowledgeNodeRef] = Field(default_factory=list)
    # Mastery slice (narrative-pathways MM-A). Advisory typed context projected
    # by the composition root from the kernel basis fold: which of the account
    # map's skills are done (>= honed) and which are review-flagged (raw minutes
    # met the honed bar but confidence-weighted basis did not). Never a gate -
    # it shapes what the Strategist is *asked to propose*, disposed by the MM-C
    # output gate (``08-mastery-memory.md``). Defaults keep today's behavior.
    mastered_node_ids: list[KnowledgeNodeId] = Field(default_factory=list)
    review_node_ids: list[KnowledgeNodeId] = Field(default_factory=list)
    max_review_modules: int = Field(default=2, gt=0, le=10)
    max_review_minutes: int = Field(default=60, gt=0)

    @model_validator(mode="after")
    def _priority_values_unique_nonempty(self) -> StrategyConstraints:
        if not self.required_priority_values:
            raise ValueError("required_priority_values must be non-empty")
        if len(set(self.required_priority_values)) != len(self.required_priority_values):
            raise ValueError("required_priority_values must not contain duplicates")
        return self

    @model_validator(mode="after")
    def _unfilled_slots_require_pathway(self) -> StrategyConstraints:
        if self.unfilled_slots and self.pathway_id is None:
            raise ValueError("unfilled_slots requires pathway_id (no pathway selected)")
        return self

    @model_validator(mode="after")
    def _unfilled_slot_ids_unique(self) -> StrategyConstraints:
        dupes = find_duplicates([s.slot_id for s in self.unfilled_slots])
        if dupes:
            raise ValueError(f"unfilled_slots must have unique slot_id values; duplicates: {dupes}")
        return self

    @model_validator(mode="after")
    def _knowledge_nodes_require_pathway(self) -> StrategyConstraints:
        # A knowledge-map vocabulary exists only for a selected pathway (a map
        # requires a selection, ``06-…`` d6); a vocabulary with no pathway is
        # contradictory, exactly like ``unfilled_slots``.
        if self.knowledge_nodes and self.pathway_id is None:
            raise ValueError("knowledge_nodes requires pathway_id (no pathway selected)")
        return self

    @model_validator(mode="after")
    def _knowledge_node_ids_unique(self) -> StrategyConstraints:
        dupes = find_duplicates([n.node_id for n in self.knowledge_nodes])
        if dupes:
            raise ValueError(
                f"knowledge_nodes must have unique node_id values; duplicates: {dupes}"
            )
        return self

    @model_validator(mode="after")
    def _mastery_lists_require_pathway(self) -> StrategyConstraints:
        # Mastery data exists only for a selected pathway (no selection -> no map
        # -> no mastery projection); a slice with no pathway is contradictory,
        # exactly like ``knowledge_nodes`` and ``unfilled_slots``.
        if (self.mastered_node_ids or self.review_node_ids) and self.pathway_id is None:
            raise ValueError(
                "mastered_node_ids/review_node_ids require pathway_id "
                "(no pathway selected)"
            )
        return self

    @model_validator(mode="after")
    def _mastery_ids_unique(self) -> StrategyConstraints:
        for field_name, ids in (
            ("mastered_node_ids", self.mastered_node_ids),
            ("review_node_ids", self.review_node_ids),
        ):
            dupes = find_duplicates(ids)
            if dupes:
                raise ValueError(
                    f"{field_name} must have unique node ids; duplicates: {dupes}"
                )
        return self

    @model_validator(mode="after")
    def _mastery_lists_disjoint(self) -> StrategyConstraints:
        # A node is either done (>= honed) or flagged for review, never both -
        # the confidence-weighted basis puts it on exactly one side of the bar.
        overlap = sorted(set(self.mastered_node_ids) & set(self.review_node_ids))
        if overlap:
            raise ValueError(
                "mastered_node_ids and review_node_ids must be disjoint; "
                f"overlap: {overlap}"
            )
        return self

    @model_validator(mode="after")
    def _mastery_ids_in_vocabulary(self) -> StrategyConstraints:
        # Every mastery id must resolve to the account map - the composition-time
        # guarantee (``08-mastery-memory.md``) backed here as a contract
        # invariant, so the MM-C gate can compare mastery ids against module tags
        # over one shared vocabulary.
        vocabulary = {n.node_id for n in self.knowledge_nodes}
        for field_name, ids in (
            ("mastered_node_ids", self.mastered_node_ids),
            ("review_node_ids", self.review_node_ids),
        ):
            unknown = sorted(set(ids) - vocabulary)
            if unknown:
                raise ValueError(
                    f"{field_name} must reference knowledge_nodes; "
                    f"unknown ids: {unknown}"
                )
        return self
