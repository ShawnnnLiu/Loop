"""Tests for the shared duplicate-detection helpers (NP-A follow-up)."""

from __future__ import annotations

from agentic_calendar.contracts._dedup import casefold_key, find_duplicates


def test_find_duplicates_returns_sorted_distinct_repeats() -> None:
    assert find_duplicates(["b", "a", "b", "a", "a"]) == ["a", "b"]


def test_find_duplicates_empty_when_all_unique() -> None:
    assert find_duplicates(["a", "b", "c"]) == []


def test_find_duplicates_handles_tuple_identity() -> None:
    keys = [("thing", "org"), ("thing", "org"), ("other", "")]
    assert find_duplicates(keys) == [("thing", "org")]


def test_casefold_key_is_case_insensitive() -> None:
    assert casefold_key("Applied-ML") == casefold_key("applied-ml")


def test_find_duplicates_after_casefold_reports_folded_form() -> None:
    folded = [casefold_key(t) for t in ["Applied-ML", "applied-ml", "rag"]]
    assert find_duplicates(folded) == ["applied-ml"]
