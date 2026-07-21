"""Skill-grouping registry: load + validate the checked-in JSON, expose lookups.

Canonical spec: ``docs/specs/skill-grouping.schema.md``.

A :class:`~agentic_calendar.contracts.skill_grouping.SkillGrouping` is a versioned
overlay **beside** the skill taxonomy: it curates, once per ``skill_id``, the
group a skill belongs to, its per-skill honed-threshold prior, and a display
blurb (``07-tree-generation.md``, KT-B). The knowledge-map generator consumes it
plus a pathway's slot seeds to emit a ``KnowledgeMap``; the runtime add-node
placement path reuses the same ``skill_id -> group`` lookup.

Like the taxonomy loader, the grouping is curated data versioned in review - a
load failure is a deployment defect, never something to paper over, so every
failure mode raises a typed :class:`SkillGroupingLoadError` instead of returning
a partial grouping.

Leaf kernel: depends only on ``common`` and ``contracts``.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from agentic_calendar.common.errors import AgenticCalendarError
from agentic_calendar.contracts.skill_grouping import (
    SkillGroup,
    SkillGrouping,
    SkillGroupingEntry,
)

DEFAULT_SKILL_GROUPING_PATH = (
    Path(__file__).resolve().parents[3] / "taxonomy" / "skill_grouping_v1.json"
)
"""The current pinned grouping version. A grouping change is a NEW file version
referenced explicitly (append-only, taxonomy discipline); the generated map
artifact stamps the loaded ``skill_grouping_version`` so drift is reviewable."""


class SkillGroupingLoadError(AgenticCalendarError):
    """The checked-in grouping file is missing, unreadable, or contract-invalid."""


def load_skill_grouping(
    path: Path = DEFAULT_SKILL_GROUPING_PATH,
) -> SkillGrouping:
    """Load and contract-validate one versioned skill-grouping file."""
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SkillGroupingLoadError(
            f"cannot read skill-grouping file {path}: {exc}"
        ) from exc
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SkillGroupingLoadError(
            f"skill-grouping file {path} is not valid JSON: {exc}"
        ) from exc
    try:
        return SkillGrouping.model_validate(payload)
    except ValidationError as exc:
        raise SkillGroupingLoadError(
            f"skill-grouping file {path} violates the SkillGrouping contract: {exc}"
        ) from exc


class SkillGroupingRegistry:
    """Read-only lookup surface over one validated skill grouping.

    ``group_id`` uniqueness and ``skill_id`` uniqueness are contract-enforced, so
    both maps are unambiguous by construction.
    """

    def __init__(self, grouping: SkillGrouping) -> None:
        self._grouping = grouping
        self._group_by_id: dict[str, SkillGroup] = {
            g.group_id: g for g in grouping.groups
        }
        self._entry_by_skill: dict[str, SkillGroupingEntry] = {
            e.skill_id: e for e in grouping.entries
        }

    @property
    def skill_grouping_version(self) -> str:
        return self._grouping.skill_grouping_version

    @property
    def taxonomy_version(self) -> str:
        return self._grouping.taxonomy_version

    @property
    def groups(self) -> list[SkillGroup]:
        return list(self._grouping.groups)

    @property
    def entries(self) -> list[SkillGroupingEntry]:
        return list(self._grouping.entries)

    def group(self, group_id: str) -> SkillGroup | None:
        return self._group_by_id.get(group_id)

    def entry_for(self, skill_id: str) -> SkillGroupingEntry | None:
        """The grouping row that places ``skill_id``, or ``None`` if unrowed.

        The generator maps ``None`` to ``SKILL_GROUPING_MISSING_ENTRY`` rather
        than synthesizing a placement (``07-tree-generation.md``).
        """
        return self._entry_by_skill.get(skill_id)

    def members_of(self, group_id: str) -> list[SkillGroupingEntry]:
        """Every entry placed in ``group_id``, in curated file order."""
        return [e for e in self._grouping.entries if e.group_id == group_id]


def load_skill_grouping_registry(
    path: Path = DEFAULT_SKILL_GROUPING_PATH,
) -> SkillGroupingRegistry:
    """Convenience: :func:`load_skill_grouping` wrapped in a registry."""
    return SkillGroupingRegistry(load_skill_grouping(path))
