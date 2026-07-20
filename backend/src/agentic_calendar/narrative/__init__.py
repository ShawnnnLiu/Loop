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

from .coverage import (
    PathwayFit,
    SlotCoverage,
    SlotState,
    pathway_fit,
    slot_coverage,
)
from .progress import SlotProgress, story_progress

__all__ = [
    "PathwayFit",
    "SlotCoverage",
    "SlotProgress",
    "SlotState",
    "pathway_fit",
    "slot_coverage",
    "story_progress",
]
