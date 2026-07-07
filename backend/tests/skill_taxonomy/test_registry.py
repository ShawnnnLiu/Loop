"""Tests for the skill-taxonomy registry loader and lookups."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agentic_calendar.contracts.career_track import CareerTrack
from agentic_calendar.skill_taxonomy import (
    DEFAULT_TAXONOMY_PATH,
    SkillTaxonomyLoadError,
    SkillTaxonomyRegistry,
    load_registry,
    load_taxonomy,
)


def test_default_path_points_at_the_checked_in_seed() -> None:
    assert DEFAULT_TAXONOMY_PATH.name == "skill_taxonomy_v1.json"
    assert DEFAULT_TAXONOMY_PATH.is_file()


def test_load_taxonomy_validates_the_seed_file() -> None:
    taxonomy = load_taxonomy()
    assert taxonomy.taxonomy_version == "skill-taxonomy-v1"
    assert len(taxonomy.entries) > 0


def test_registry_lookup_by_id_and_alias() -> None:
    registry = load_registry()
    python = registry.by_id("skill.python")
    assert python is not None and python.display_name == "Python"
    assert registry.by_alias("python3") is python
    assert registry.by_id("skill.nope") is None
    assert registry.by_alias("not-a-real-alias") is None


def test_registry_alias_index_covers_every_alias() -> None:
    registry = load_registry()
    for entry in registry.entries:
        for alias in entry.aliases:
            assert registry.by_alias(alias) is registry.by_id(entry.skill_id)


# Taxonomy v1 curates entries for the starting three tracks only; the G-I
# expansion tracks are corpus-only until entries are curated for them
# (docs/specs/skill-taxonomy.schema.md).
_TAXONOMY_V1_TRACKS = {CareerTrack.SWE, CareerTrack.MLE, CareerTrack.AI_ENGINEER}


@pytest.mark.parametrize("track", list(CareerTrack))
def test_entries_for_track_returns_exactly_the_tagged_slice(track: CareerTrack) -> None:
    registry = load_registry()
    slice_ = registry.entries_for_track(track)
    if track in _TAXONOMY_V1_TRACKS:
        assert slice_, f"track {track.value} has an empty vocabulary slice"
    assert all(track in entry.track_tags for entry in slice_)
    tagged_ids = {e.skill_id for e in registry.entries if track in e.track_tags}
    assert {e.skill_id for e in slice_} == tagged_ids


def test_missing_file_raises_typed_load_error(tmp_path: Path) -> None:
    with pytest.raises(SkillTaxonomyLoadError, match="cannot read"):
        load_taxonomy(tmp_path / "absent.json")


def test_malformed_json_raises_typed_load_error(tmp_path: Path) -> None:
    path = tmp_path / "broken.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(SkillTaxonomyLoadError, match="not valid JSON"):
        load_taxonomy(path)


def test_contract_invalid_taxonomy_raises_typed_load_error(tmp_path: Path) -> None:
    """A duplicate alias across entries breaks unambiguous resolution and
    must be rejected at load, never papered over."""
    entry = {
        "skill_id": "skill.python",
        "display_name": "Python",
        "aliases": ["python"],
        "track_tags": ["swe"],
        "kind": "language",
        "corpus_evidence": None,
    }
    path = tmp_path / "dupes.json"
    path.write_text(
        json.dumps(
            {
                "taxonomy_version": "skill-taxonomy-v1",
                "entries": [entry, {**entry, "skill_id": "skill.python-lang"}],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(SkillTaxonomyLoadError, match="globally unique"):
        load_taxonomy(path)


def test_registry_entries_property_is_a_copy() -> None:
    registry = load_registry()
    entries = registry.entries
    entries.clear()
    assert registry.entries, "mutating the returned list must not empty the registry"


def test_registry_wraps_any_valid_taxonomy() -> None:
    taxonomy = load_taxonomy()
    registry = SkillTaxonomyRegistry(taxonomy)
    assert registry.taxonomy_version == taxonomy.taxonomy_version
