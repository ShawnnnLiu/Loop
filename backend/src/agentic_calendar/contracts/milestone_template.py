"""``milestone_template`` contract.

Canonical reference: ``docs/axioms/18-caching-strategy.md`` (the ``task_template``
cache target and its "Template schema update" invalidation trigger) plus the
Phase-5c slice of ``docs/axioms/10-mvp-roadmap.md``. There is intentionally no
``docs/specs/*.schema.md`` for this skeleton seed layer, mirroring the other
Phase-5 infrastructure contracts (``strategy_constraints``, ``cache_key``).

A :class:`MilestoneTemplate` is a deterministic *seed* for a :class:`GoalClass`:
a small ordered set of :class:`Milestone`s that later expand into
``SyllabusModule``s. Templates are canned, validated literals owned by the
``templates/`` leaf registry (the single source of truth for which goal class
maps to which template); this module only defines their *shape*.
``template_schema_version`` feeds ``CacheKey.object_schema_version`` for
``CacheTarget.TASK_TEMPLATE`` entries, so bumping it invalidates cached work
derived from the template (axiom 18).

LLMs do not author templates; this is deterministic infrastructure.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .common_types import Priority


class GoalClass(StrEnum):
    """Career-preparation goal classes that have a milestone template."""

    COLLEGE_ADMISSIONS = "college_admissions"
    GRADUATE_ADMISSIONS = "graduate_admissions"
    CAREER_TRANSITION = "career_transition"


class Milestone(BaseModel):
    """One deterministic seed milestone within a :class:`MilestoneTemplate`.

    A milestone is anchored relative to the goal deadline
    (``offset_days_before_deadline``) and carries the same ``priority`` and
    ``target_outcomes`` shape as a ``SyllabusModule`` so it can later seed one.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    milestone_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    offset_days_before_deadline: int = Field(ge=0)
    target_outcomes: list[str] = Field(min_length=1)
    priority: Priority
    default_estimated_total_min: int = Field(gt=0)


class MilestoneTemplate(BaseModel):
    """A canned, ordered set of milestones for one :class:`GoalClass`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    template_id: str = Field(min_length=1)
    goal_class: GoalClass
    template_schema_version: str = Field(min_length=1)
    milestones: list[Milestone] = Field(min_length=1)

    @model_validator(mode="after")
    def _milestone_ids_unique(self) -> MilestoneTemplate:
        ids = [m.milestone_id for m in self.milestones]
        if len(set(ids)) != len(ids):
            raise ValueError("milestones must have unique milestone_id values")
        return self
