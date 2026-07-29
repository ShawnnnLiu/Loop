"""Registry-level invariants for the curated skill grouping (KT-B).

The Pydantic contract (``skill_grouping.py``) enforces only shape (unique ids,
declared groups). The content invariants the spec assigns to the generator /
registry tests (``skill-grouping.schema.md`` "Contract vs. Registry") live here,
mirroring ``tests/templates/test_pathway_registry.py``:

- ``taxonomy_version`` matches the pinned taxonomy;
- every entry's ``skill_id`` resolves against that taxonomy;
- **demand-driven coverage** (``07-tree-generation.md``): a row for every skill
  reachable from any seed pathway's slot seeds *and* for the whole add-picker
  slice of each live track - the widened coverage stated loudly;
- no prestige terms in any text field (the extraction adapter's denylist reused
  as the single source of truth);
- every declared group is used (no dead groups).
"""

from __future__ import annotations

from agentic_calendar.contracts._dedup import casefold_key, find_duplicates
from agentic_calendar.contracts.career_track import CareerTrack
from agentic_calendar.llm_nodes.anthropic_adapter import _CATEGORY_DENYLIST
from agentic_calendar.skill_taxonomy import (
    load_registry,
    load_skill_grouping,
    load_skill_grouping_registry,
)
from agentic_calendar.templates import list_pathways

#: Tracks whose add-picker slice the grouping must cover (the live seed tracks).
_LIVE_TRACKS = (CareerTrack.SWE, CareerTrack.MLE, CareerTrack.AI_ENGINEER)


def _seed_skill_ids() -> set[str]:
    """Every skill reachable from a registered pathway's slot seeds."""
    return {
        skill_id
        for pathway in list_pathways()
        for slot in pathway.evidence_slots
        for skill_id in slot.branch_skill_ids
    }


def _add_picker_slice() -> set[str]:
    """The union of every live track's taxonomy slice - the add-node vocabulary."""
    registry = load_registry()
    return {
        entry.skill_id
        for track in _LIVE_TRACKS
        for entry in registry.entries_for_track(track)
    }


def test_grouping_loads_and_is_pinned() -> None:
    grouping = load_skill_grouping()
    assert grouping.skill_grouping_version == "skill-grouping-v2"


def test_grouping_taxonomy_version_matches_the_pinned_taxonomy() -> None:
    grouping = load_skill_grouping()
    assert grouping.taxonomy_version == load_registry().taxonomy_version


def test_group_and_skill_ids_are_unique() -> None:
    grouping = load_skill_grouping()
    assert find_duplicates([g.group_id for g in grouping.groups]) == []
    assert find_duplicates([e.skill_id for e in grouping.entries]) == []


def test_every_entry_skill_id_resolves_against_the_pinned_taxonomy() -> None:
    registry = load_registry()
    for entry in load_skill_grouping().entries:
        assert registry.by_id(entry.skill_id) is not None, entry.skill_id


def test_every_entry_group_is_declared() -> None:
    grouping = load_skill_grouping()
    declared = {g.group_id for g in grouping.groups}
    for entry in grouping.entries:
        assert entry.group_id in declared, entry.skill_id


def test_every_declared_group_is_used() -> None:
    """No dead groups: a declared group with no member skill is a curation slip."""
    grouping = load_skill_grouping()
    used = {e.group_id for e in grouping.entries}
    dead = [g.group_id for g in grouping.groups if g.group_id not in used]
    assert dead == [], dead


def test_covers_every_seed_pathway_skill() -> None:
    """Demand-driven coverage: a seeded skill without a row would fail generation
    (``SKILL_GROUPING_MISSING_ENTRY``)."""
    registry = load_skill_grouping_registry()
    missing = sorted(s for s in _seed_skill_ids() if registry.entry_for(s) is None)
    assert missing == [], f"seed skills without a grouping row: {missing}"


def test_covers_the_whole_add_picker_slice_of_every_live_track() -> None:
    """The widened coverage (``07-tree-generation.md``): the same
    ``skill_id -> group`` lookup places runtime add-node picks, so every skill a
    live track's picker can offer must have a row."""
    registry = load_skill_grouping_registry()
    missing = sorted(s for s in _add_picker_slice() if registry.entry_for(s) is None)
    assert missing == [], f"add-picker skills without a grouping row: {missing}"


def test_grouping_has_no_rows_outside_the_add_picker_slice() -> None:
    """The grouping curates the live vocabulary and nothing beyond it - a row for
    a skill no live track offers is dead weight."""
    slice_ids = _add_picker_slice()
    extra = sorted(
        e.skill_id for e in load_skill_grouping().entries if e.skill_id not in slice_ids
    )
    assert extra == [], f"grouping rows outside the live slice: {extra}"


def test_no_prestige_terms_in_any_text_field() -> None:
    grouping = load_skill_grouping()
    texts: list[str] = []
    for group in grouping.groups:
        texts.extend([group.title, group.blurb])
    for entry in grouping.entries:
        texts.append(entry.blurb)
    for text in texts:
        folded = casefold_key(text)
        for term in _CATEGORY_DENYLIST:
            assert casefold_key(term) not in folded, f"prestige term {term!r} in {text!r}"


def test_expected_minutes_are_positive_priors() -> None:
    for entry in load_skill_grouping().entries:
        assert entry.expected_minutes >= 1, entry.skill_id
