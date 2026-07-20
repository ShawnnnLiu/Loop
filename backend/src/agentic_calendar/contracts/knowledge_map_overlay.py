"""``knowledge_map_overlay`` contracts (KT-A).

Canonical spec: ``docs/specs/knowledge-map-overlay.schema.md``.

An account's knowledge map is the generated :class:`KnowledgeMap`(s) of its
selected pathway(s) plus an append-only overlay of the six ``frozen`` record
types defined here (house pattern: ``TaskDispositionRecord``). All six are
deterministic and never LLM-touched; no free-text field on any record ever
enters a prompt (the personal-content injection wall, stated in the spec).

This module defines only the *shape*: id patterns, field bounds and text caps,
``credit_minutes > 0``, timezone-aware timestamps, and the taxonomy-anchored
rule on :attr:`MasteryGrant.node_id`. Per-account count caps
(``<= 5`` custom groups, ``<= 20`` custom nodes, one note per node) and
uniqueness of custom ids are store/API concerns (KT-C,
``CUSTOM_CONTENT_LIMIT_EXCEEDED``), not single-object invariants.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from .common_types import MasteryGrantSource, MasteryTier

# A generated (taxonomy-anchored / capstone) map node.
GeneratedNodeId = Annotated[str, StringConstraints(pattern=r"^kn-[a-z0-9-]+$")]
# A user-created personal node.
CustomNodeId = Annotated[str, StringConstraints(pattern=r"^kcn-[a-z0-9-]+$")]
# A user-created personal group.
CustomGroupId = Annotated[str, StringConstraints(pattern=r"^kcg-[a-z0-9-]+$")]
# Any node - a generated node or a custom node.
AnyNodeId = Annotated[str, StringConstraints(pattern=r"^k(n|cn)-[a-z0-9-]+$")]
# Any group a custom node may sit in - a generated group or a custom group.
AnyGroupId = Annotated[str, StringConstraints(pattern=r"^k(g|cg)-[a-z0-9-]+$")]


def _require_aware(value: datetime, field: str) -> datetime:
    if value.tzinfo is None:
        raise ValueError(f"{field} must be timezone-aware")
    return value


class NodeAddition(BaseModel):
    """The user added a taxonomy skill we did not seed (pathway content).

    Placement is deterministic (the skill's ``skill-grouping`` row names the
    group); this record only stores *what* was added and when.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    user_id: str = Field(min_length=1)
    skill_id: str = Field(min_length=1)
    created_at: datetime

    @model_validator(mode="after")
    def _created_at_aware(self) -> NodeAddition:
        _require_aware(self.created_at, "created_at")
        return self


class CustomGroup(BaseModel):
    """A user-created personal group (personal content; counts toward nothing)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    user_id: str = Field(min_length=1)
    custom_group_id: CustomGroupId
    name: str = Field(min_length=1, max_length=60)
    created_at: datetime

    @model_validator(mode="after")
    def _created_at_aware(self) -> CustomGroup:
        _require_aware(self.created_at, "created_at")
        return self


class CustomNode(BaseModel):
    """A user-created personal node (personal content; counts toward nothing)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    user_id: str = Field(min_length=1)
    custom_node_id: CustomNodeId
    name: str = Field(min_length=1, max_length=60)
    description: str | None = Field(default=None, max_length=500)
    group_id: AnyGroupId
    created_at: datetime

    @model_validator(mode="after")
    def _created_at_aware(self) -> CustomNode:
        _require_aware(self.created_at, "created_at")
        return self


class NodeNote(BaseModel):
    """One free-text note on any node (personal content; never in any prompt)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    user_id: str = Field(min_length=1)
    node_id: AnyNodeId
    text: str = Field(min_length=1, max_length=2000)
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def _timestamps_aware(self) -> NodeNote:
        _require_aware(self.created_at, "created_at")
        _require_aware(self.updated_at, "updated_at")
        return self


class MasteryGrant(BaseModel):
    """Mastery-basis credit from onboarding / evidence confirmation.

    Pathway content, and the only mastery record onboarding may write. The
    ``node_id`` is a generated (taxonomy-anchored) node only: a grant has no
    meaning on a personal node, so a ``kcn-`` id is rejected at parse time.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    user_id: str = Field(min_length=1)
    node_id: GeneratedNodeId
    credit_minutes: int = Field(gt=0)
    source: MasteryGrantSource
    created_at: datetime

    @model_validator(mode="after")
    def _created_at_aware(self) -> MasteryGrant:
        _require_aware(self.created_at, "created_at")
        return self


class MasterySetPoint(BaseModel):
    """The explicit per-node user control - the only record that can lower
    mastery. Applies to any node; on a custom node it caps at ``honed`` (a
    store/kernel concern, KT-B - the contract accepts any ``MasteryTier``)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    user_id: str = Field(min_length=1)
    node_id: AnyNodeId
    target_tier: MasteryTier
    created_at: datetime

    @model_validator(mode="after")
    def _created_at_aware(self) -> MasterySetPoint:
        _require_aware(self.created_at, "created_at")
        return self
