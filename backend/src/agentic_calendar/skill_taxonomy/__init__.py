"""Skill-taxonomy kernel (résumé intake RI-B, axiom 08 "Controlled Vocabularies").

Deterministic access to the checked-in skill vocabulary
(``backend/taxonomy/skill_taxonomy_v1.json``): a validating registry loader
with id/alias/track lookups, a pure surface normalizer + alias resolver, and
the deterministic role→track mapping. The LLM never touches the vocabulary —
extraction nodes emit surface strings, and this kernel maps them onto the
canonical entries (or reports them unmatched; nothing is silently promoted).

Leaf kernel: depends only on ``common`` and ``contracts``. The service layer
(RI-C) imports it; ``llm_nodes/`` never does — the allowed weak-spot
vocabulary and the membership resolver reach the node as plain data
(``.importlinter`` enforces both directions).
"""

from .grouping import (
    DEFAULT_SKILL_GROUPING_PATH,
    SkillGroupingLoadError,
    SkillGroupingRegistry,
    load_skill_grouping,
    load_skill_grouping_registry,
)
from .normalize import normalize_surface, resolve, resolve_track
from .registry import (
    DEFAULT_TAXONOMY_PATH,
    SkillTaxonomyLoadError,
    SkillTaxonomyRegistry,
    load_registry,
    load_taxonomy,
)

__all__ = [
    "DEFAULT_SKILL_GROUPING_PATH",
    "DEFAULT_TAXONOMY_PATH",
    "SkillGroupingLoadError",
    "SkillGroupingRegistry",
    "SkillTaxonomyLoadError",
    "SkillTaxonomyRegistry",
    "load_registry",
    "load_skill_grouping",
    "load_skill_grouping_registry",
    "load_taxonomy",
    "normalize_surface",
    "resolve",
    "resolve_track",
]
