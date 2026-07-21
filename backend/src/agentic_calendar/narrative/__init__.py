"""``narrative/`` — deterministic pathway fit, gaps, and story progress (NP-B).

A leaf kernel, like ``prerequisites/``: pure functions over ``contracts/`` +
``common/`` only, imported by the service layer / composition root (never the
other way). It owns the deterministic answer to "which pathway pillars does the
user's confirmed evidence fill, and which is the active plan building toward?" -
LLMs never rank pathways or assign fit (axiom 00). The registry of
:class:`PathwayTemplate` literals lives in ``templates/pathways.py``; this kernel
computes over whichever template it is handed.
"""

from __future__ import annotations

from .account_map import merge_additions, pathway_node_vocabulary
from .coverage import (
    PathwayFit,
    SlotCoverage,
    SlotState,
    pathway_fit,
    slot_coverage,
)
from .generation import (
    ADVISORY_MIN_SKILL_NODES,
    LOOP_SKILL_NODE_CEILING,
    MapGenerationError,
    generate_map,
    node_id_for,
)
from .mastery import (
    DEFAULT_MASTERY_TUNING,
    MasteryTuning,
    folded_basis,
    map_state,
)
from .progress import SlotProgress, story_progress

__all__ = [
    "ADVISORY_MIN_SKILL_NODES",
    "DEFAULT_MASTERY_TUNING",
    "LOOP_SKILL_NODE_CEILING",
    "MapGenerationError",
    "MasteryTuning",
    "PathwayFit",
    "SlotCoverage",
    "SlotProgress",
    "SlotState",
    "folded_basis",
    "generate_map",
    "map_state",
    "merge_additions",
    "node_id_for",
    "pathway_fit",
    "pathway_node_vocabulary",
    "slot_coverage",
    "story_progress",
]
