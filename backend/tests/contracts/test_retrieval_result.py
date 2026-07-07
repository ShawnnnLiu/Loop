"""Tests for the ``RetrievalResult`` contract (determinism rule enforcement)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from agentic_calendar.contracts.retrieval_query import RetrievalQuery
from agentic_calendar.contracts.retrieval_result import (
    CHUNK_ID_PATTERN,
    RankedChunk,
    RetrievalResult,
)
from tests._fixture_loader import iter_invalid, iter_valid

CONTRACT = "retrieval_result"


@pytest.mark.parametrize("fixture", list(iter_valid(CONTRACT)), ids=lambda f: f.name)
def test_valid_fixture_parses(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    result = RetrievalResult.model_validate(payload)
    assert result.snapshot_id == payload["snapshot_id"]
    assert len(result.results) == len(payload["results"])


@pytest.mark.parametrize("fixture", list(iter_invalid(CONTRACT)), ids=lambda f: f.name)
def test_invalid_fixture_rejected(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    expected = fixture.expected  # type: ignore[attr-defined]
    with pytest.raises(ValidationError) as exc_info:
        RetrievalResult.model_validate(payload)
    msg = str(exc_info.value)
    for substr in expected["error_substrings"]:
        assert substr in msg, f"expected substring {substr!r} not in:\n{msg}"


def test_chunk_id_pattern_matches_the_chunker_derivation() -> None:
    # Single canonical pattern: the chunker imports this exact object.
    from agentic_calendar.retrieval import CHUNK_ID_PATTERN as reexported

    assert reexported is CHUNK_ID_PATTERN


def test_empty_results_are_a_valid_honest_miss() -> None:
    result = RetrievalResult(
        snapshot_id="snap_7d3a91c04b5e2f68",
        query=RetrievalQuery(query_text="no such thing", k=5),
        results=[],
    )
    assert result.results == []


def test_models_are_frozen() -> None:
    entry = RankedChunk(
        rank=1,
        chunk_id="chunk_9e21c04b5e2f68d3",
        doc_id="doc_2f6c1b8a9d4e0357",
        ordinal=0,
        score=1.0,
        start_char=0,
        end_char=10,
    )
    with pytest.raises(ValidationError):
        entry.score = 2.0  # type: ignore[misc]
