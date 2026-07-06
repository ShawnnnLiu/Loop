"""Tests for the ``RetrievalQuery`` contract."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from agentic_calendar.contracts.career_track import CareerTrack
from agentic_calendar.contracts.retrieval_query import MAX_RETRIEVAL_K, RetrievalQuery
from tests._fixture_loader import iter_invalid, iter_valid

CONTRACT = "retrieval_query"


@pytest.mark.parametrize("fixture", list(iter_valid(CONTRACT)), ids=lambda f: f.name)
def test_valid_fixture_parses(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    query = RetrievalQuery.model_validate(payload)
    assert query.query_text == payload["query_text"]


@pytest.mark.parametrize("fixture", list(iter_invalid(CONTRACT)), ids=lambda f: f.name)
def test_invalid_fixture_rejected(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    expected = fixture.expected  # type: ignore[attr-defined]
    with pytest.raises(ValidationError) as exc_info:
        RetrievalQuery.model_validate(payload)
    msg = str(exc_info.value)
    for substr in expected["error_substrings"]:
        assert substr in msg, f"expected substring {substr!r} not in:\n{msg}"


def test_track_defaults_to_none_and_k_cap_is_exposed() -> None:
    query = RetrievalQuery(query_text="graph algorithms", k=MAX_RETRIEVAL_K)
    assert query.track is None
    assert query.k == 100


def test_track_accepts_every_career_track() -> None:
    for track in CareerTrack:
        assert RetrievalQuery(query_text="q", track=track, k=1).track is track
