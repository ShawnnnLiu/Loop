"""Committed knowledge-map artifact: load + attach to pathway templates (KT-B).

The deterministic generator (``narrative.generation.generate_map``) emits one
:class:`KnowledgeMap` per pathway; the build tool
(``tools/generate_knowledge_maps.py``) writes them to a single committed
artifact (``backend/pathways/knowledge_maps.json``), the ``export_schemas``
doctrine verbatim: deterministic generator, committed output, drift reviewable
in PRs. This module is the *runtime* reader - it loads the reviewed artifact and
attaches each map to its :class:`PathwayTemplate`, exactly as
``07-tree-generation.md`` specifies. Nothing here generates a map; runtime only
serves what review approved (plus the per-account overlay, KT-B/KT-C).

Attachment rebuilds the frozen template through ``model_validate`` (never a bare
``model_copy(update=...)``; house rule), so the composed object is validated by
the ordinary KT-A :class:`PathwayTemplate` contract.

Leaf kernel: depends only on ``common`` and ``contracts``. The load is lazy and
cached, so importing the pathway registry never triggers file I/O - the build
tool can regenerate the artifact without a bootstrap cycle.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from pydantic import ValidationError

from agentic_calendar.common.errors import AgenticCalendarError
from agentic_calendar.contracts.knowledge_map import KnowledgeMap
from agentic_calendar.contracts.pathway_template import PathwayTemplate

from .pathways import get_pathway

DEFAULT_KNOWLEDGE_MAPS_PATH = (
    Path(__file__).resolve().parents[3] / "pathways" / "knowledge_maps.json"
)
"""The committed, generated map artifact keyed by ``pathway_id``."""


class KnowledgeMapsLoadError(AgenticCalendarError):
    """The committed map artifact is missing, unreadable, or contract-invalid."""


def load_knowledge_maps(
    path: Path = DEFAULT_KNOWLEDGE_MAPS_PATH,
) -> dict[str, KnowledgeMap]:
    """Load and contract-validate the committed ``pathway_id -> KnowledgeMap`` artifact."""
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise KnowledgeMapsLoadError(
            f"cannot read knowledge-maps artifact {path}: {exc}"
        ) from exc
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise KnowledgeMapsLoadError(
            f"knowledge-maps artifact {path} is not valid JSON: {exc}"
        ) from exc
    maps = payload.get("maps")
    if not isinstance(maps, dict):
        raise KnowledgeMapsLoadError(
            f"knowledge-maps artifact {path} has no 'maps' object"
        )
    try:
        return {
            pathway_id: KnowledgeMap.model_validate(body)
            for pathway_id, body in maps.items()
        }
    except ValidationError as exc:
        raise KnowledgeMapsLoadError(
            f"knowledge-maps artifact {path} violates the KnowledgeMap contract: {exc}"
        ) from exc


@lru_cache(maxsize=1)
def _cached_maps() -> dict[str, KnowledgeMap]:
    return load_knowledge_maps()


def knowledge_map_for(pathway_id: str) -> KnowledgeMap | None:
    """The generated map for ``pathway_id``, or ``None`` if none is committed."""
    return _cached_maps().get(pathway_id)


def pathway_with_map(pathway_id: str) -> PathwayTemplate | None:
    """``get_pathway`` with its generated ``knowledge_map`` attached, or ``None``.

    The map is grafted onto the frozen template via ``model_validate`` so the
    returned object is a fully validated :class:`PathwayTemplate`.
    """
    template = get_pathway(pathway_id)
    if template is None:
        return None
    kmap = knowledge_map_for(pathway_id)
    if kmap is None:
        return template
    data = template.model_dump()
    data["knowledge_map"] = kmap.model_dump()
    return PathwayTemplate.model_validate(data)
