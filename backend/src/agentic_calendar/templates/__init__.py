"""``templates/`` — deterministic curated-literal registries (leaf kernel).

Two registries of canned, review-gated literals live here, both depending only
on ``common/`` and ``contracts/``:

* the Phase-5c milestone-template registry (``registry.py``): one
  :class:`MilestoneTemplate` per :class:`GoalClass` (see
  ``docs/axioms/18-caching-strategy.md`` for how ``template_schema_version``
  drives ``task_template`` cache invalidation); and
* the narrative-pathways pathway registry (``pathways.py``, NP-B): the curated
  :class:`PathwayTemplate` literals and their track-scoped theme vocabulary,
  over which the ``narrative/`` kernel computes pathway fit deterministically.
"""

from __future__ import annotations

from agentic_calendar.contracts.milestone_template import (
    GoalClass,
    Milestone,
    MilestoneTemplate,
)
from agentic_calendar.contracts.pathway_template import EvidenceSlot, PathwayTemplate

from .pathways import (
    PATHWAY_REGISTRY_VERSION,
    PATHWAY_SCHEMA_VERSION,
    get_pathway,
    is_theme_in_vocabulary,
    list_pathways,
    pathways_for_track,
    theme_vocabulary,
)
from .registry import (
    TEMPLATE_SCHEMA_VERSION,
    get_template,
    list_templates,
    select_template_for_profile,
)

__all__ = [
    "PATHWAY_REGISTRY_VERSION",
    "PATHWAY_SCHEMA_VERSION",
    "TEMPLATE_SCHEMA_VERSION",
    "EvidenceSlot",
    "GoalClass",
    "Milestone",
    "MilestoneTemplate",
    "PathwayTemplate",
    "get_pathway",
    "get_template",
    "is_theme_in_vocabulary",
    "list_pathways",
    "list_templates",
    "pathways_for_track",
    "select_template_for_profile",
    "theme_vocabulary",
]
