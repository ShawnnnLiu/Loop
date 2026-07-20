"""Tests for the FTS5 chunk index.

Determinism is the load-bearing property: same query + same snapshot →
byte-identical results, ties broken by (score desc, chunk_id asc), every
result stamped with its snapshot. No network, no LLM, tmp-file SQLite only.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from agentic_calendar.common.sqlite import SqliteDatabase
from agentic_calendar.contracts.career_track import CareerTrack
from agentic_calendar.contracts.corpus_document import (
    CorpusDocument,
    content_hash_for,
    derive_doc_id,
)
from agentic_calendar.contracts.corpus_snapshot import ChunkingParams, CorpusSnapshot
from agentic_calendar.contracts.retrieval_query import RetrievalQuery
from agentic_calendar.contracts.source_claim import SourceType
from agentic_calendar.retrieval import (
    SnapshotNotIndexedError,
    SqliteChunkIndex,
    SqliteCorpusRegistry,
    compile_match_expression,
    compile_phrase_expression,
    fts5_available,
)
from agentic_calendar.retrieval import index as index_module
from agentic_calendar.retrieval.errors import Fts5UnavailableError

_COLLECTED = date(2026, 7, 6)
_CREATED_AT = datetime(2026, 7, 6, 18, 0, tzinfo=UTC)
_PARAMS = ChunkingParams(algorithm="structure_v1", target_chars=200, overlap_chars=0)

_DOCS: dict[str, tuple[str, tuple[CareerTrack, ...]]] = {
    "https://example.com/system-design": (
        "System design interviews reward structured thinking.\n"
        "Practice designing a URL shortener and a news feed.\n"
        "Capacity estimation and sharding come up constantly.",
        (CareerTrack.SWE,),
    ),
    "https://example.com/ml-pipelines": (
        "Machine learning pipelines need reproducible feature engineering.\n"
        "Training-serving skew is the classic production failure.\n"
        "Monitor data drift after every deployment.",
        (CareerTrack.MLE,),
    ),
    "https://example.com/eval-harnesses": (
        "Evaluation harnesses for LLM systems pin prompts and grade outputs.\n"
        "System prompts change; recorded evals keep the baseline honest.",
        (CareerTrack.AI_ENGINEER, CareerTrack.MLE),
    ),
}


def _corpus(tmp_path: Path) -> tuple[SqliteCorpusRegistry, CorpusSnapshot]:
    registry = SqliteCorpusRegistry(SqliteDatabase(tmp_path / "corpus.db"))
    doc_ids = []
    for url, (text, tracks) in _DOCS.items():
        document = CorpusDocument(
            doc_id=derive_doc_id(url, _COLLECTED),
            source_url=url,
            source_type=SourceType.UNCLASSIFIED,
            license_note="Public page; test fixture.",
            date_collected=_COLLECTED,
            track_tags=list(tracks),
            content_hash=content_hash_for(text),
            title=url.rsplit("/", 1)[-1],
        )
        registry.register(document, text=text)
        doc_ids.append(document.doc_id)
    snapshot = registry.create_snapshot(
        doc_ids, created_at=_CREATED_AT, chunking_params=_PARAMS
    )
    return registry, snapshot


@pytest.fixture
def built(tmp_path: Path) -> tuple[SqliteChunkIndex, SqliteCorpusRegistry, CorpusSnapshot]:
    registry, snapshot = _corpus(tmp_path)
    index = SqliteChunkIndex(SqliteDatabase(tmp_path / "index.db"))
    index.build(registry, snapshot)
    return index, registry, snapshot


def test_fts5_is_available_in_this_environment() -> None:
    # The one-line CI verification the plan calls for: this suite IS the
    # check — if the interpreter's SQLite lacks FTS5 this fails loudly.
    assert fts5_available()


def test_missing_fts5_is_a_typed_setup_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(index_module, "fts5_available", lambda: False)
    with pytest.raises(Fts5UnavailableError):
        SqliteChunkIndex(SqliteDatabase(tmp_path / "index.db"))


def test_build_is_idempotent(
    built: tuple[SqliteChunkIndex, SqliteCorpusRegistry, CorpusSnapshot],
) -> None:
    index, registry, snapshot = built
    first = index.build(registry, snapshot)
    assert first > 0
    assert index.build(registry, snapshot) == first
    assert index.is_built(snapshot.snapshot_id)


def test_search_unbuilt_snapshot_is_typed(tmp_path: Path) -> None:
    index = SqliteChunkIndex(SqliteDatabase(tmp_path / "index.db"))
    with pytest.raises(SnapshotNotIndexedError):
        index.search(
            RetrievalQuery(query_text="anything", k=5),
            snapshot_id="snap_0000000000000000",
        )


def test_search_is_deterministic_and_snapshot_stamped(
    built: tuple[SqliteChunkIndex, SqliteCorpusRegistry, CorpusSnapshot],
) -> None:
    index, _, snapshot = built
    query = RetrievalQuery(query_text="system design interviews", k=5)
    first = index.search(query, snapshot_id=snapshot.snapshot_id)
    second = index.search(query, snapshot_id=snapshot.snapshot_id)
    assert first.model_dump_json() == second.model_dump_json()  # byte-identical
    assert first.snapshot_id == snapshot.snapshot_id
    assert first.query == query
    assert first.results
    top = first.results[0]
    assert top.doc_id == derive_doc_id("https://example.com/system-design", _COLLECTED)


def test_scores_are_ordered_and_ranks_contiguous(
    built: tuple[SqliteChunkIndex, SqliteCorpusRegistry, CorpusSnapshot],
) -> None:
    index, _, snapshot = built
    result = index.search(
        RetrievalQuery(query_text="production systems design", k=10),
        snapshot_id=snapshot.snapshot_id,
    )
    scores = [entry.score for entry in result.results]
    assert scores == sorted(scores, reverse=True)
    assert [entry.rank for entry in result.results] == list(
        range(1, len(result.results) + 1)
    )


def test_exact_score_ties_break_by_chunk_id_ascending(tmp_path: Path) -> None:
    # Two documents with identical-length, same-term chunks produce exact
    # BM25 ties; the deterministic order is then chunk_id ascending.
    registry = SqliteCorpusRegistry(SqliteDatabase(tmp_path / "corpus.db"))
    text = "Sharding strategies for databases."
    doc_ids = []
    for url in ("https://example.com/t1", "https://example.com/t2"):
        document = CorpusDocument(
            doc_id=derive_doc_id(url, _COLLECTED),
            source_url=url,
            source_type=SourceType.UNCLASSIFIED,
            license_note="Public page; test fixture.",
            date_collected=_COLLECTED,
            track_tags=[CareerTrack.SWE],
            content_hash=content_hash_for(text + " " + url),
            title=url,
        )
        registry.register(document, text=text + " " + url)
        doc_ids.append(document.doc_id)
    snapshot = registry.create_snapshot(
        doc_ids, created_at=_CREATED_AT, chunking_params=_PARAMS
    )
    index = SqliteChunkIndex(SqliteDatabase(tmp_path / "index.db"))
    index.build(registry, snapshot)

    result = index.search(
        RetrievalQuery(query_text="sharding", k=5), snapshot_id=snapshot.snapshot_id
    )

    assert len(result.results) == 2
    assert result.results[0].score == result.results[1].score
    assert result.results[0].chunk_id < result.results[1].chunk_id


def test_track_filter_scopes_the_search(
    built: tuple[SqliteChunkIndex, SqliteCorpusRegistry, CorpusSnapshot],
) -> None:
    index, _, snapshot = built
    ml_doc = derive_doc_id("https://example.com/ml-pipelines", _COLLECTED)
    eval_doc = derive_doc_id("https://example.com/eval-harnesses", _COLLECTED)

    unfiltered = index.search(
        RetrievalQuery(query_text="pipelines evals production", k=10),
        snapshot_id=snapshot.snapshot_id,
    )
    mle_only = index.search(
        RetrievalQuery(query_text="pipelines evals production", track=CareerTrack.MLE, k=10),
        snapshot_id=snapshot.snapshot_id,
    )
    swe_only = index.search(
        RetrievalQuery(query_text="pipelines evals production", track=CareerTrack.SWE, k=10),
        snapshot_id=snapshot.snapshot_id,
    )

    assert {e.doc_id for e in mle_only.results} <= {ml_doc, eval_doc}
    assert mle_only.results  # the MLE-tagged docs still match
    assert all(e.doc_id not in {ml_doc, eval_doc} for e in swe_only.results)
    assert len(unfiltered.results) >= len(mle_only.results)


def test_k_bounds_the_result_count(
    built: tuple[SqliteChunkIndex, SqliteCorpusRegistry, CorpusSnapshot],
) -> None:
    index, _, snapshot = built
    result = index.search(
        RetrievalQuery(query_text="design pipelines evals systems", k=1),
        snapshot_id=snapshot.snapshot_id,
    )
    assert len(result.results) == 1


def test_no_word_tokens_is_an_honest_empty_result(
    built: tuple[SqliteChunkIndex, SqliteCorpusRegistry, CorpusSnapshot],
) -> None:
    index, _, snapshot = built
    result = index.search(
        RetrievalQuery(query_text="!!! ???", k=5), snapshot_id=snapshot.snapshot_id
    )
    assert result.results == []


def test_fts5_operators_in_query_text_are_literals(
    built: tuple[SqliteChunkIndex, SqliteCorpusRegistry, CorpusSnapshot],
) -> None:
    index, _, snapshot = built
    # NEAR/AND/quotes would be FTS5 syntax if unquoted; compiled form treats
    # them as plain tokens and must not raise.
    result = index.search(
        RetrievalQuery(query_text='NEAR(design AND "systems")', k=5),
        snapshot_id=snapshot.snapshot_id,
    )
    assert result.results  # "design"/"systems" still match as bag-of-words


def test_get_chunk_round_trips_provenance(
    built: tuple[SqliteChunkIndex, SqliteCorpusRegistry, CorpusSnapshot],
) -> None:
    index, registry, snapshot = built
    result = index.search(
        RetrievalQuery(query_text="system design", k=1),
        snapshot_id=snapshot.snapshot_id,
    )
    entry = result.results[0]
    chunk = index.get_chunk(snapshot.snapshot_id, entry.chunk_id)
    assert chunk is not None
    assert chunk.doc_id == entry.doc_id
    assert (chunk.start_char, chunk.end_char) == (entry.start_char, entry.end_char)
    # The auditability chain: the chunk text is the exact document slice.
    text = registry.get_text(entry.doc_id)
    assert text is not None
    assert chunk.text == text[entry.start_char : entry.end_char]
    assert index.get_chunk(snapshot.snapshot_id, "chunk_0000000000000000") is None


def test_compile_match_expression_is_quoted_bag_of_words() -> None:
    assert compile_match_expression("System-design, C++!") == '"system" OR "design" OR "c"'
    assert compile_match_expression("...") == ""


def test_compile_phrase_expression_is_one_quoted_phrase() -> None:
    assert compile_phrase_expression("Power BI") == '"power bi"'
    # Punctuation-only tokens vanish under tokenization (the documented
    # ``c++`` → ``c`` noise); no word tokens compiles to the empty expression.
    assert compile_phrase_expression("c++") == '"c"'
    assert compile_phrase_expression("...") == ""
    # FTS5 operators are inside the quotes — literals, never syntax.
    assert compile_phrase_expression('NEAR(design AND "systems")') == '"near design and systems"'


def test_match_phrase_requires_adjacent_tokens(
    built: tuple[SqliteChunkIndex, SqliteCorpusRegistry, CorpusSnapshot],
) -> None:
    index, _, snapshot = built
    sd_doc = derive_doc_id("https://example.com/system-design", _COLLECTED)
    matches = index.match_phrase(snapshot.snapshot_id, "system design")
    assert matches and all(doc_id == sd_doc for _, doc_id in matches)
    # Both words occur in the document ("System design …", "Capacity
    # estimation …") but never adjacent — bag-of-words would match, the
    # phrase must not.
    assert index.match_phrase(snapshot.snapshot_id, "system estimation") == []
    assert index.match_phrase(snapshot.snapshot_id, "!!!") == []


def test_match_phrase_track_filter_is_any_of(
    built: tuple[SqliteChunkIndex, SqliteCorpusRegistry, CorpusSnapshot],
) -> None:
    index, _, snapshot = built
    ml_doc = derive_doc_id("https://example.com/ml-pipelines", _COLLECTED)
    assert index.match_phrase(
        snapshot.snapshot_id, "machine learning", tracks=[CareerTrack.SWE]
    ) == []
    mle = index.match_phrase(
        snapshot.snapshot_id, "machine learning", tracks=[CareerTrack.MLE]
    )
    assert mle and all(doc_id == ml_doc for _, doc_id in mle)
    # Multi-track scope is an OR: adding an unrelated track loses nothing.
    assert (
        index.match_phrase(
            snapshot.snapshot_id,
            "machine learning",
            tracks=[CareerTrack.SWE, CareerTrack.MLE],
        )
        == mle
    )


def test_match_phrase_is_deterministic_and_ordered(
    built: tuple[SqliteChunkIndex, SqliteCorpusRegistry, CorpusSnapshot],
) -> None:
    index, _, snapshot = built
    first = index.match_phrase(snapshot.snapshot_id, "design")
    second = index.match_phrase(snapshot.snapshot_id, "design")
    assert first == second
    assert [c for c, _ in first] == sorted(c for c, _ in first)


def test_match_phrase_unbuilt_snapshot_is_typed(tmp_path: Path) -> None:
    index = SqliteChunkIndex(SqliteDatabase(tmp_path / "index.db"))
    with pytest.raises(SnapshotNotIndexedError):
        index.match_phrase("snap_0000000000000000", "anything")


def test_two_snapshots_score_independently(tmp_path: Path) -> None:
    # BM25 statistics must be per snapshot: indexing a second snapshot must
    # not change the first snapshot's byte-exact results.
    registry, snapshot = _corpus(tmp_path)
    index = SqliteChunkIndex(SqliteDatabase(tmp_path / "index.db"))
    index.build(registry, snapshot)
    query = RetrievalQuery(query_text="system design interviews", k=5)
    before = index.search(query, snapshot_id=snapshot.snapshot_id)

    other_params = ChunkingParams(
        algorithm="structure_v1", target_chars=120, overlap_chars=0
    )
    second = registry.create_snapshot(
        snapshot.doc_ids, created_at=_CREATED_AT, chunking_params=other_params
    )
    index.build(registry, second)
    after = index.search(query, snapshot_id=snapshot.snapshot_id)

    assert before.model_dump_json() == after.model_dump_json()
