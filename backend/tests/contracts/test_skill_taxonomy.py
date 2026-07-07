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
