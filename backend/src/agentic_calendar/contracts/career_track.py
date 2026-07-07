"""``CareerTrack`` — the shared closed career-track enum.

Canonical spec: ``docs/specs/skill-taxonomy.schema.md``.

The literal connection point between the skill taxonomy and the planned
grounding-RAG corpus: taxonomy entries and corpus documents are both
track-tagged with this enum, so corpus-derived evidence can later join
against taxonomy entries deterministically. Whichever feature needs a new
track adds it here, in review — the enum is closed, never LLM-extended.
"""

from __future__ import annotations

from enum import StrEnum


class CareerTrack(StrEnum):
    """Closed set of career tracks the product plans for."""

    SWE = "swe"
    MLE = "mle"
    AI_ENGINEER = "ai_engineer"
