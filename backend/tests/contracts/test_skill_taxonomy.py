"""Tests for the ``SkillTaxonomy`` contract and the checked-in seed vocabulary.

Each fixture under ``tests/fixtures/{valid,invalid}/skill_taxonomy/`` becomes
a parametrized test case. The seed file tests pin the curated
``backend/taxonomy/skill_taxonomy_v1.json`` to the contract so the vocabulary
can never drift invalid.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from agentic_calendar.contracts.career_track import CareerTrack
from agentic_calendar.contracts.skill_taxonomy import SkillTaxonomy
from tests._fixture_loader import iter_invalid, iter_valid

CONTRACT = "skill_taxonomy"

SEED_PATH = Path(__file__).parents[2] / "taxonomy" / "skill_taxonomy_v1.json"
SEED_V2_PATH = Path(__file__).parents[2] / "taxonomy" / "skill_taxonomy_v2.json"
SEED_V3_PATH = Path(__file__).parents[2] / "taxonomy" / "skill_taxonomy_v3.json"


@pytest.mark.parametrize(
    "fixture",
    list(iter_valid(CONTRACT)),
    ids=lambda f: f.name,
)
def test_valid_fixture_parses(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    taxonomy = SkillTaxonomy.model_validate(payload)
    assert taxonomy.taxonomy_version == payload["taxonomy_version"]


@pytest.mark.parametrize(
    "fixture",
    list(iter_invalid(CONTRACT)),
    ids=lambda f: f.name,
)
def test_invalid_fixture_rejected(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    expected = fixture.expected  # type: ignore[attr-defined]
    with pytest.raises(ValidationError) as exc_info:
        SkillTaxonomy.model_validate(payload)
    msg = str(exc_info.value)
    for substr in expected["error_substrings"]:
        assert substr in msg, (
            f"expected substring {substr!r} not in error message:\n{msg}"
        )


def test_taxonomy_is_frozen() -> None:
    taxonomy = SkillTaxonomy.model_validate(next(iter_valid(CONTRACT)).payload)
    with pytest.raises(ValidationError):
        taxonomy.taxonomy_version = "skill-taxonomy-v2"  # type: ignore[misc]


def test_unknown_field_rejected() -> None:
    payload = next(iter_valid(CONTRACT)).payload | {"confidence": 1.0}
    with pytest.raises(ValidationError) as exc_info:
        SkillTaxonomy.model_validate(payload)
    assert "confidence" in str(exc_info.value)


class TestSeedTaxonomy:
    """The checked-in v1 seed is curated data; pin it to the contract."""

    @pytest.fixture(scope="class")
    def seed(self) -> SkillTaxonomy:
        payload = json.loads(SEED_PATH.read_text(encoding="utf-8"))
        return SkillTaxonomy.model_validate(payload)

    def test_seed_file_is_contract_valid(self, seed: SkillTaxonomy) -> None:
        assert seed.taxonomy_version == "skill-taxonomy-v1"

    def test_seed_track_slices_meet_plan_minimums(self, seed: SkillTaxonomy) -> None:
        counts = {
            track: sum(1 for e in seed.entries if track in e.track_tags)
            for track in CareerTrack
        }
        assert counts[CareerTrack.SWE] >= 60
        assert counts[CareerTrack.MLE] >= 30
        assert counts[CareerTrack.AI_ENGINEER] >= 30

    def test_seed_carries_no_corpus_evidence_yet(self, seed: SkillTaxonomy) -> None:
        # v1 predates the RI-F enrichment tool; evidence must be absent, not
        # fabricated.
        assert all(e.corpus_evidence is None for e in seed.entries)


class TestSeedTaxonomyV2:
    """The checked-in v2 seed (data_analyst expansion) is curated data; pin
    it to the contract and to the append-only versioning discipline."""

    @pytest.fixture(scope="class")
    def seed_v1(self) -> SkillTaxonomy:
        payload = json.loads(SEED_PATH.read_text(encoding="utf-8"))
        return SkillTaxonomy.model_validate(payload)

    @pytest.fixture(scope="class")
    def seed(self) -> SkillTaxonomy:
        payload = json.loads(SEED_V2_PATH.read_text(encoding="utf-8"))
        return SkillTaxonomy.model_validate(payload)

    def test_seed_file_is_contract_valid(self, seed: SkillTaxonomy) -> None:
        assert seed.taxonomy_version == "skill-taxonomy-v2"

    def test_data_analyst_slice_meets_plan_bounds(self, seed: SkillTaxonomy) -> None:
        count = sum(
            1 for e in seed.entries if CareerTrack.DATA_ANALYST in e.track_tags
        )
        # Career profile estimates ~35; the résumé-intake prompt budget caps
        # any track slice at ~100 display names.
        assert 30 <= count <= 100

    def test_v2_is_append_only_over_v1(
        self, seed: SkillTaxonomy, seed_v1: SkillTaxonomy
    ) -> None:
        by_id = {e.skill_id: e for e in seed.entries}
        v1_alias_home = {
            alias: e.skill_id for e in seed_v1.entries for alias in e.aliases
        }
        for entry in seed_v1.entries:
            successor = by_id.get(entry.skill_id)
            assert successor is not None, f"{entry.skill_id} dropped in v2"
            assert set(entry.aliases) <= set(successor.aliases)
            assert set(entry.track_tags) <= set(successor.track_tags)
            assert entry.kind == successor.kind
        for alias, home in v1_alias_home.items():
            v2_home = next(
                e.skill_id for e in seed.entries if alias in e.aliases
            )
            assert v2_home == home, f"alias {alias!r} re-homed in v2"

    def test_seed_carries_no_corpus_evidence_yet(self, seed: SkillTaxonomy) -> None:
        # RI-F enrichment has not run against v2; evidence must be absent,
        # not fabricated.
        assert all(e.corpus_evidence is None for e in seed.entries)


class TestSeedTaxonomyV3:
    """The checked-in v3 seed (data_scientist expansion) is curated data;
    pin it to the contract and to the append-only versioning discipline."""

    @pytest.fixture(scope="class")
    def seed_v2(self) -> SkillTaxonomy:
        payload = json.loads(SEED_V2_PATH.read_text(encoding="utf-8"))
        return SkillTaxonomy.model_validate(payload)

    @pytest.fixture(scope="class")
    def seed(self) -> SkillTaxonomy:
        payload = json.loads(SEED_V3_PATH.read_text(encoding="utf-8"))
        return SkillTaxonomy.model_validate(payload)

    def test_seed_file_is_contract_valid(self, seed: SkillTaxonomy) -> None:
        assert seed.taxonomy_version == "skill-taxonomy-v3"

    def test_data_scientist_slice_meets_plan_bounds(self, seed: SkillTaxonomy) -> None:
        count = sum(
            1 for e in seed.entries if CareerTrack.DATA_SCIENTIST in e.track_tags
        )
        # Career profile estimates ~56; the résumé-intake prompt budget caps
        # any track slice at ~100 display names.
        assert 30 <= count <= 100

    def test_every_track_slice_stays_inside_prompt_budget(
        self, seed: SkillTaxonomy
    ) -> None:
        # The résumé-intake prompt embeds the resolved track's display names;
        # RI docs bound that slice at ~100 short strings.
        for track in CareerTrack:
            count = sum(1 for e in seed.entries if track in e.track_tags)
            assert count <= 100, f"{track.value} slice {count} breaches budget"

    def test_v3_is_append_only_over_v2(
        self, seed: SkillTaxonomy, seed_v2: SkillTaxonomy
    ) -> None:
        by_id = {e.skill_id: e for e in seed.entries}
        v2_alias_home = {
            alias: e.skill_id for e in seed_v2.entries for alias in e.aliases
        }
        for entry in seed_v2.entries:
            successor = by_id.get(entry.skill_id)
            assert successor is not None, f"{entry.skill_id} dropped in v3"
            assert set(entry.aliases) <= set(successor.aliases)
            assert set(entry.track_tags) <= set(successor.track_tags)
            assert entry.kind == successor.kind
        for alias, home in v2_alias_home.items():
            v3_home = next(
                e.skill_id for e in seed.entries if alias in e.aliases
            )
            assert v3_home == home, f"alias {alias!r} re-homed in v3"

    def test_seed_carries_no_corpus_evidence_yet(self, seed: SkillTaxonomy) -> None:
        # RI-F enrichment has not run against v3; evidence must be absent,
        # not fabricated.
        assert all(e.corpus_evidence is None for e in seed.entries)
