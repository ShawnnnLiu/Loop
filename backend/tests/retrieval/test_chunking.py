"""Tests for ``structure_v1`` chunking.

The load-bearing property is at the top: re-chunking pinned text is
byte-identical, and every chunk is an exact contiguous slice of the input —
the auditability + reproducibility contract the snapshot pin depends on.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from itertools import pairwise

import pytest

from agentic_calendar.contracts.career_track import CareerTrack
from agentic_calendar.contracts.corpus_document import (
    CorpusDocument,
    content_hash_for,
    derive_doc_id,
)
from agentic_calendar.contracts.corpus_snapshot import ChunkingParams
from agentic_calendar.contracts.source_claim import SourceType
from agentic_calendar.retrieval import (
    CHUNK_ID_PATTERN,
    DEFAULT_CHUNKING_PARAMS,
    InMemoryCorpusRegistry,
    UnknownCorpusDocumentError,
    chunk_snapshot,
    chunk_text,
    derive_chunk_id,
    normalize_text,
)

_DOC_ID = "doc_0123456789abcdef"

_PARAMS = ChunkingParams(algorithm="structure_v1", target_chars=80, overlap_chars=20)

# Markdown-ish plain text: headings, paragraphs, a deep section. Normalized
# once so offsets refer to exactly what a registry would store.
_MARKDOWN = normalize_text(
    """
# Guide

Intro paragraph one, short.

Intro paragraph two, also short.

## Preparation

Preparation body sentence one is here.

Preparation body sentence two is here.

### Details

Detail line.
"""
)

# HTML-derived shape: one line per source block element, no blank lines.
_HTML_DERIVED = "\n".join(
    f"Line {i} of a web page paragraph, block element number {i}."
    for i in range(12)
)


def _assert_well_formed(text: str, params: ChunkingParams) -> None:
    chunks = chunk_text(text, doc_id=_DOC_ID, params=params)
    assert [c.ordinal for c in chunks] == list(range(len(chunks)))
    for chunk in chunks:
        assert CHUNK_ID_PATTERN.match(chunk.chunk_id)
        assert chunk.chunk_id == derive_chunk_id(_DOC_ID, chunk.ordinal, params)
        # The auditability invariant: an exact contiguous slice.
        assert chunk.text == text[chunk.start_char : chunk.end_char]
        assert chunk.text
        # Soft target + bounded overlap: never larger than target + overlap
        # unless a single unit was oversized (hard-split keeps units <= target,
        # so the bound holds universally for these fixtures).
        assert len(chunk.text) <= params.target_chars + params.overlap_chars


def test_rechunking_is_byte_identical() -> None:
    first = chunk_text(_MARKDOWN, doc_id=_DOC_ID, params=_PARAMS)
    second = chunk_text(_MARKDOWN, doc_id=_DOC_ID, params=_PARAMS)
    assert first == second


def test_chunks_are_exact_slices_and_well_formed() -> None:
    _assert_well_formed(_MARKDOWN, _PARAMS)
    _assert_well_formed(_HTML_DERIVED, _PARAMS)
    _assert_well_formed(_MARKDOWN, DEFAULT_CHUNKING_PARAMS)


def test_full_text_is_covered_in_order() -> None:
    chunks = chunk_text(_MARKDOWN, doc_id=_DOC_ID, params=_PARAMS)
    # Chunk cores advance strictly; together (with overlaps) they cover every
    # non-blank character of the document.
    ends = [c.end_char for c in chunks]
    assert ends == sorted(ends)
    assert len(set(ends)) == len(ends)
    covered = set()
    for chunk in chunks:
        covered.update(range(chunk.start_char, chunk.end_char))
    uncovered = [
        i for i in range(len(_MARKDOWN)) if i not in covered and _MARKDOWN[i] != "\n"
    ]
    assert uncovered == []


def test_headings_bound_sections_and_stack_into_breadcrumbs() -> None:
    chunks = chunk_text(_MARKDOWN, doc_id=_DOC_ID, params=_PARAMS)
    by_breadcrumb = {c.breadcrumb for c in chunks}
    assert "Guide" in by_breadcrumb
    assert "Guide > Preparation" in by_breadcrumb
    assert "Guide > Preparation > Details" in by_breadcrumb
    # No chunk spans a section boundary: text before "## Preparation" and the
    # heading itself never share a chunk with the "# Guide" intro paragraphs.
    prep_start = _MARKDOWN.index("## Preparation")
    for chunk in chunks:
        assert not (chunk.start_char < prep_start < chunk.end_char)


def test_sibling_heading_replaces_stack_level() -> None:
    text = normalize_text("## A\n\nBody a.\n\n## B\n\nBody b.")
    chunks = chunk_text(text, doc_id=_DOC_ID, params=_PARAMS)
    assert {c.breadcrumb for c in chunks} == {"A", "B"}


def test_text_without_headings_has_no_breadcrumb() -> None:
    chunks = chunk_text(_HTML_DERIVED, doc_id=_DOC_ID, params=_PARAMS)
    assert chunks
    assert {c.breadcrumb for c in chunks} == {None}


def test_html_derived_text_splits_at_line_boundaries() -> None:
    chunks = chunk_text(_HTML_DERIVED, doc_id=_DOC_ID, params=_PARAMS)
    assert len(chunks) > 1
    for chunk in chunks:
        # Every chunk starts at a line start, not mid-line (line fallback).
        assert chunk.start_char == 0 or _HTML_DERIVED[chunk.start_char - 1] == "\n"


def test_oversized_single_line_is_hard_split() -> None:
    text = "x" * 250
    chunks = chunk_text(text, doc_id=_DOC_ID, params=_PARAMS)
    assert [c.text for c in chunks] == ["x" * 80, "x" * 80, "x" * 80, "x" * 10]


def test_overlap_extends_backward_within_bounds() -> None:
    chunks = chunk_text(_HTML_DERIVED, doc_id=_DOC_ID, params=_PARAMS)
    for previous, current in pairwise(chunks):
        overlap = previous.end_char - current.start_char
        assert overlap <= _PARAMS.overlap_chars
        assert current.end_char > previous.end_char


def test_zero_overlap_yields_disjoint_chunks() -> None:
    params = ChunkingParams(algorithm="structure_v1", target_chars=80, overlap_chars=0)
    chunks = chunk_text(_HTML_DERIVED, doc_id=_DOC_ID, params=params)
    for previous, current in pairwise(chunks):
        assert current.start_char >= previous.end_char


def test_different_params_change_every_chunk_id() -> None:
    other = ChunkingParams(algorithm="structure_v1", target_chars=81, overlap_chars=20)
    first = {c.chunk_id for c in chunk_text(_MARKDOWN, doc_id=_DOC_ID, params=_PARAMS)}
    second = {c.chunk_id for c in chunk_text(_MARKDOWN, doc_id=_DOC_ID, params=other)}
    assert first & second == set()


def test_empty_text_yields_no_chunks() -> None:
    assert chunk_text("", doc_id=_DOC_ID, params=_PARAMS) == []


# --------------------------------------------------------------------------- #
# chunk_snapshot: pure function of (registry, snapshot).
# --------------------------------------------------------------------------- #

_COLLECTED = date(2026, 7, 6)
_CREATED_AT = datetime(2026, 7, 6, 18, 0, tzinfo=UTC)


def _register(registry: InMemoryCorpusRegistry, url: str, text: str) -> CorpusDocument:
    document = CorpusDocument(
        doc_id=derive_doc_id(url, _COLLECTED),
        source_url=url,
        source_type=SourceType.UNCLASSIFIED,
        license_note="Public page; test fixture.",
        date_collected=_COLLECTED,
        track_tags=[CareerTrack.SWE],
        content_hash=content_hash_for(text),
        title="Test document",
    )
    registry.register(document, text=text)
    return document


def test_chunk_snapshot_uses_pinned_params_and_canonical_order() -> None:
    registry = InMemoryCorpusRegistry()
    a = _register(registry, "https://example.com/a", _MARKDOWN)
    b = _register(registry, "https://example.com/b", _HTML_DERIVED)
    snapshot = registry.create_snapshot(
        [b.doc_id, a.doc_id], created_at=_CREATED_AT, chunking_params=_PARAMS
    )

    chunks = chunk_snapshot(registry, snapshot)

    assert chunks == chunk_snapshot(registry, snapshot)  # deterministic
    doc_order = list(dict.fromkeys(c.doc_id for c in chunks))
    assert doc_order == snapshot.doc_ids  # canonical (sorted) member order
    expected_a = chunk_text(_MARKDOWN, doc_id=a.doc_id, params=_PARAMS)
    assert [c for c in chunks if c.doc_id == a.doc_id] == expected_a


def test_chunk_snapshot_missing_member_is_typed() -> None:
    registry = InMemoryCorpusRegistry()
    a = _register(registry, "https://example.com/a", _MARKDOWN)
    snapshot = registry.create_snapshot(
        [a.doc_id], created_at=_CREATED_AT, chunking_params=_PARAMS
    )
    empty = InMemoryCorpusRegistry()
    with pytest.raises(UnknownCorpusDocumentError) as exc_info:
        chunk_snapshot(empty, snapshot)
    assert exc_info.value.doc_ids == [a.doc_id]
