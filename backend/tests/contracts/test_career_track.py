"""Tests for the shared ``CareerTrack`` enum.

The member values are a cross-plan contract: corpus documents
(``track_tags``) and the planned résumé-intake skill taxonomy both consume
this exact set, so a rename or removal here breaks data on both sides.
Additions are fine; this test pins the existing values and their order.
"""

from __future__ import annotations

from agentic_calendar.contracts.career_track import CareerTrack


def test_member_values_are_pinned() -> None:
    assert [track.value for track in CareerTrack] == ["swe", "mle", "ai_engineer"]


def test_values_round_trip_from_strings() -> None:
    for track in CareerTrack:
        assert CareerTrack(track.value) is track
