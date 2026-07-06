"""Tests for the ``CorpusDocument`` contract and its derivation helpers."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from agentic_calendar.contracts.corpus_document import (
    CorpusDocument,
    content_hash_for,
    derive_doc_id,
)
from tests._fixture_loader import iter_invalid, iter_valid

CONTRACT = "corpus_document"


@pytest.mark.parametrize("fixture", list(iter_valid(CONTRACT)), ids=lambda f: f.name)
def test_valid_fixture_parses(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    document = CorpusDocument.model_validate(payload)
    assert document.doc_id == payload["doc_id"]


@pytest.mark.parametrize("fixture", list(iter_invalid(CONTRACT)), ids=lambda f: f.name)
def test_invalid_fixture_rejected(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    expected = fixture.expected  # type: ignore[attr-defined]
    with pytest.raises(ValidationError) as exc_info:
        CorpusDocument.model_validate(payload)
    msg = str(exc_info.value)
    for substr in expected["error_substrings"]:
        assert substr in msg, f"expected substring {substr!r} not in:\n{msg}"


def test_content_hash_for_is_plain_sha256() -> None:
    # Known vector: sha256 of the empty string.
    assert content_hash_for("") == (
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    )


def test_derive_doc_id_is_deterministic_and_well_formed() -> None:
    a = derive_doc_id("https://example.com/x", date(2026, 7, 6))
    assert a == derive_doc_id("https://example.com/x", date(2026, 7, 6))
    assert a.startswith("doc_")
    assert len(a) == len("doc_") + 16


def test_derive_doc_id_varies_with_url_and_date() -> None:
    base = derive_doc_id("https://example.com/x", date(2026, 7, 6))
    assert derive_doc_id("https://example.com/y", date(2026, 7, 6)) != base
    # The same URL fetched on a new day is a new document (pages change).
    assert derive_doc_id("https://example.com/x", date(2026, 7, 7)) != base
