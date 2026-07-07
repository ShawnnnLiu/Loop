"""``CareerTrack`` — the shared closed track enum.

Two surfaces consume this one module:

* corpus documents tag their ``track_tags`` from it
  (``docs/specs/corpus-document.schema.md``, grounding layer), and
* the résumé-intake skill taxonomy scopes its entries by it
  (``docs/specs/skill-taxonomy.schema.md``, résumé intake).

It is deliberately tiny and closed: tracks are added here in review, never
free-typed and never invented by an LLM. Keep it dependency-free so both
consumers stay decoupled.
"""

from __future__ import annotations

from enum import StrEnum


class CareerTrack(StrEnum):
    """Closed set of supported career-preparation tracks."""

    SWE = "swe"
    MLE = "mle"
    AI_ENGINEER = "ai_engineer"
    QUANT_DEV = "quant_dev"
    DATA_SCIENTIST = "data_scientist"
    PRODUCT_MANAGER = "product_manager"
