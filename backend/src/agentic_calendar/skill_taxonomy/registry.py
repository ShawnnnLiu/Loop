"""Taxonomy registry: load + validate the checked-in JSON, expose lookups.

Canonical spec: ``docs/specs/skill-taxonomy.schema.md``.

The vocabulary is curated data, versioned in review — a load failure is a
deployment defect, never something to paper over, so every failure mode
raises a typed :class:`SkillTaxonomyLoadError` instead of returning a
partial vocabulary.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from agentic_calendar.common.errors import AgenticCalendarError
from agentic_calendar.contracts.career_track import CareerTrack
from agentic_calendar.contracts.skill_taxonomy import SkillEntry, SkillTaxonomy

DEFAULT_TAXONOMY_PATH = (
    Path(__file__).resolve().parents[3] / "taxonomy" / "skill_taxonomy_v1.json"
)
"""The current pinned vocabulary version. A vocabulary change is a NEW file
version referenced explicitly (append-only, like the eval sets); consumers
stamp the loaded ``taxonomy_version`` on their outputs."""


class SkillTaxonomyLoadError(AgenticCalendarError):
    """The checked-in taxonomy file is missing, unreadable, or contract-invalid."""


def load_taxonomy(path: Path = DEFAULT_TAXONOMY_PATH) -> SkillTaxonomy:
    """Load and contract-validate one versioned taxonomy file."""
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SkillTaxonomyLoadError(f"cannot read taxonomy file {path}: {exc}") from exc
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SkillTaxonomyLoadError(f"taxonomy file {path} is not valid JSON: {exc}") from exc
    try:
        return SkillTaxonomy.model_validate(payload)
    except ValidationError as exc:
        raise SkillTaxonomyLoadError(
            f"taxonomy file {path} violates the SkillTaxonomy contract: {exc}"
        ) from exc


class SkillTaxonomyRegistry:
    """Read-only lookup surface over one validated taxonomy.

    Alias keys are exactly the stored aliases (already lowercase-normalized,
    contract-enforced); global alias uniqueness makes :meth:`by_alias`
    unambiguous by construction. Callers normalize free-text surfaces with
    :func:`~agentic_calendar.skill_taxonomy.normalize.normalize_surface`
    before lookup (or use :func:`~agentic_calendar.skill_taxonomy.normalize.resolve`).
    """

    def __init__(self, taxonomy: SkillTaxonomy) -> None:
        self._taxonomy = taxonomy
        self._by_id: dict[str, SkillEntry] = {e.skill_id: e for e in taxonomy.entries}
        self._by_alias: dict[str, SkillEntry] = {
            alias: entry for entry in taxonomy.entries for alias in entry.aliases
        }

    @property
    def taxonomy_version(self) -> str:
        return self._taxonomy.taxonomy_version

    @property
    def entries(self) -> list[SkillEntry]:
        return list(self._taxonomy.entries)

    def by_id(self, skill_id: str) -> SkillEntry | None:
        return self._by_id.get(skill_id)

    def by_alias(self, alias: str) -> SkillEntry | None:
        """Exact lookup of an already-normalized alias; ``None`` when unmatched."""
        return self._by_alias.get(alias)

    def entries_for_track(self, track: CareerTrack) -> list[SkillEntry]:
        """The track-relevant taxonomy slice, in curated file order."""
        return [e for e in self._taxonomy.entries if track in e.track_tags]


def load_registry(path: Path = DEFAULT_TAXONOMY_PATH) -> SkillTaxonomyRegistry:
    """Convenience: :func:`load_taxonomy` wrapped in a registry."""
    return SkillTaxonomyRegistry(load_taxonomy(path))
