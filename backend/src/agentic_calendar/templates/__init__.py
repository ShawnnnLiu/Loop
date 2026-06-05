"""``templates/`` — deterministic milestone-template registry (leaf kernel).

Phase-5c skeleton seed layer: one :class:`MilestoneTemplate` per
:class:`GoalClass`. Depends only on ``common/`` and ``contracts/``. See
``docs/axioms/18-caching-strategy.md`` for how ``template_schema_version`` drives
``task_template`` cache invalidation.
"""

from __future__ import annotations

from agentic_calendar.contracts.milestone_template import (
    GoalClass,
    Milestone,
    MilestoneTemplate,
)

from .registry import (
    TEMPLATE_SCHEMA_VERSION,
    get_template,
    list_templates,
    select_template_for_profile,
)

__all__ = [
    "TEMPLATE_SCHEMA_VERSION",
    "GoalClass",
    "Milestone",
    "MilestoneTemplate",
    "get_template",
    "list_templates",
    "select_template_for_profile",
]
