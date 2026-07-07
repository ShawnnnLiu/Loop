"""Hybrid fusion tests (G-E).

RRF arithmetic is verified by hand; the searcher is exercised end-to-end
over a tiny real corpus with deterministic fake vectors seeded straight into
the cache — no embedding provider anywhere near these tests.
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
    FusionParams,
    HybridSearcher,
    MissingEmbeddingsError,
    SqliteChunkIndex,
    SqliteCorpusRegistry,
    SqliteVectorStore,
    reciprocal_rank_fusion,
)

_COLLECTED = date(2026, 7, 6)
_CREATED_AT = datetime(2026, 7, 6, 18, 0, tzinfo=UTC)
_PARAMS = ChunkingParams(algorithm="structure_v1", target_chars=400, overlap_chars=0)
_MODEL = "voyage-3.5"

_DOCS: dict[str, tuple[str, tuple[CareerTrack, ...]]] = {
    "https://example.com/system-design": (
        "System design interviews reward structured thinking and practice.",
        (CareerTrack.SWE,),
    ),
    "https://example.com/ml-pipelines": (
        "Machine learning pipelines need reproducible feature engineering.",
        (CareerTrack.MLE,),
    ),
}


# --------------------------------------------------------------------------- #
# Reciprocal rank fusion — hand-computed.
# --------------------------------------------------------------------------- #


def test_rrf_hand_computed_mass() -> None:
    mass = reciprocal_rank_fusion([["a", "b", "c"], ["b", "a"]], rrf_k=60)
    assert mass["a"] == pytest.approx(1 / 61 + 1 / 62)
    assert mass["b"] == pytest.approx(1 / 62 + 1 / 61)
    assert mass["c"] == pytest.approx(1 / 63)
    # a and b carry exactly equal mass (float addition is commutative) —
    # downstream ordering must fall to the chunk_id tie-break.
    assert mass["a"] == mass["b"]


def test_rrf_single_arm_and_empty() -> None:
    assert reciprocal_rank_fusion([], rrf_k=60) == {}
    assert reciprocal_rank_fusion([["x"]], rrf_k=9) == {"x": pytest.approx(1 / 10)}


# --------------------------------------------------------------------------- #
# HybridSearcher end-to-end over a tiny corpus with seeded vectors.
# --------------------------------------------------------------------------- #


def _built(
    tmp_path: Path,
) -> tuple[SqliteChunkIndex, SqliteVectorStore, SqliteCorpusRegistry, CorpusSnapshot]:
    db = SqliteDatabase(tmp_path / "corpus.db")
    registry = SqliteCorpusRegistry(db)
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
    index = SqliteChunkIndex(db)
    index.build(registry, snapshot)
    return index, SqliteVectorStore(db), registry, snapshot


def _seed_vectors(
    index: SqliteChunkIndex,
    vectors: SqliteVectorStore,
    snapshot_id: str,
    *,
    query_text: str,
    query_vector: list[float],
    vector_for_text: dict[str, list[float]],
    default: list[float],
) -> None:
    """Cache a vector per chunk (by substring match) + the query vector."""
    entries = []
    for chunk in index.list_chunks(snapshot_id):
        vector = default
        for needle, chosen in vector_for_text.items():
            if needle in chunk.text:
                vector = chosen
        entries.append((content_hash_for(chunk.text), vector))
    vectors.put_many(entries, model_name=_MODEL, input_type="document")
    vectors.put_many(
        [(content_hash_for(query_text), query_vector)],
        model_name=_MODEL,
        input_type="query",
    )


def test_hybrid_is_deterministic_and_contract_valid(tmp_path: Path) -> None:
    index, vectors, _, snapshot = _built(tmp_path)
    query_text = "system design interviews"
    _seed_vectors(
        index,
        vectors,
        snapshot.snapshot_id,
        query_text=query_text,
        query_vector=[1.0, 0.0],
        vector_for_text={"System design": [1.0, 0.0]},
        default=[0.0, 1.0],
    )
    searcher = HybridSearcher(index, vectors, model_name=_MODEL)
    query = RetrievalQuery(query_text=query_text, k=5)
    first = searcher.search(query, snapshot_id=snapshot.snapshot_id)
    second = searcher.search(query, snapshot_id=snapshot.snapshot_id)
    assert first.model_dump() == second.model_dump()
    assert first.snapshot_id == snapshot.snapshot_id
    assert first.results, "both arms rank the system-design chunk"
    swe_doc_id = derive_doc_id("https://example.com/system-design", _COLLECTED)
    assert first.results[0].doc_id == swe_doc_id


def test_dense_arm_carries_a_bm25_miss(tmp_path: Path) -> None:
    """A query whose words match nothing still retrieves via vectors."""
    index, vectors, _, snapshot = _built(tmp_path)
    query_text = "distributed architecture whiteboard rounds"  # no FTS overlap
    _seed_vectors(
        index,
        vectors,
        snapshot.snapshot_id,
        query_text=query_text,
        query_vector=[1.0, 0.0],
        vector_for_text={"System design": [1.0, 0.0]},
        default=[0.0, 1.0],
    )
    searcher = HybridSearcher(index, vectors, model_name=_MODEL)
    result = searcher.search(
        RetrievalQuery(query_text=query_text, k=2), snapshot_id=snapshot.snapshot_id
    )
    assert result.results, "dense arm must rank even when BM25 finds nothing"
    top_chunk = index.get_chunk(snapshot.snapshot_id, result.results[0].chunk_id)
    assert top_chunk is not None and "System design" in top_chunk.text


def test_track_filter_applies_to_both_arms(tmp_path: Path) -> None:
    index, vectors, _, snapshot = _built(tmp_path)
    query_text = "engineering practice"
    # The SWE doc's vector matches the query perfectly — but the track filter
    # must exclude it from the MLE-scoped candidate universe entirely.
    _seed_vectors(
        index,
        vectors,
        snapshot.snapshot_id,
        query_text=query_text,
        query_vector=[1.0, 0.0],
        vector_for_text={"System design": [1.0, 0.0]},
        default=[0.5, 0.5],
    )
    searcher = HybridSearcher(index, vectors, model_name=_MODEL)
    result = searcher.search(
        RetrievalQuery(query_text=query_text, track=CareerTrack.MLE, k=5),
        snapshot_id=snapshot.snapshot_id,
    )
    swe_doc_id = derive_doc_id("https://example.com/system-design", _COLLECTED)
    assert all(entry.doc_id != swe_doc_id for entry in result.results)
    assert result.results, "the MLE doc still ranks"


def test_missing_query_vector_is_typed(tmp_path: Path) -> None:
    index, vectors, _, snapshot = _built(tmp_path)
    _seed_vectors(
        index,
        vectors,
        snapshot.snapshot_id,
        query_text="some other query",
        query_vector=[1.0],
        vector_for_text={},
        default=[1.0],
    )
    searcher = HybridSearcher(index, vectors, model_name=_MODEL)
    with pytest.raises(MissingEmbeddingsError) as excinfo:
        searcher.search(
            RetrievalQuery(query_text="never embedded", k=3),
            snapshot_id=snapshot.snapshot_id,
        )
    assert excinfo.value.input_type == "query"


def test_missing_chunk_vectors_are_typed_never_silent_bm25(tmp_path: Path) -> None:
    index, vectors, _, snapshot = _built(tmp_path)
    query_text = "system design"
    # Only the query vector is cached; every chunk vector is missing.
    vectors.put_many(
        [(content_hash_for(query_text), [1.0])],
        model_name=_MODEL,
        input_type="query",
    )
    searcher = HybridSearcher(index, vectors, model_name=_MODEL)
    with pytest.raises(MissingEmbeddingsError) as excinfo:
        searcher.search(
            RetrievalQuery(query_text=query_text, k=3),
            snapshot_id=snapshot.snapshot_id,
        )
    assert excinfo.value.input_type == "document"
    assert excinfo.value.missing_count == len(
        index.list_chunks(snapshot.snapshot_id)
    )


def test_fusion_params_are_recorded_and_bounded(tmp_path: Path) -> None:
    index, vectors, _, _snapshot = _built(tmp_path)
    searcher = HybridSearcher(
        index, vectors, model_name=_MODEL, params=FusionParams(rrf_k=10, candidate_depth=7)
    )
    assert searcher.params.rrf_k == 10
    assert searcher.params.candidate_depth == 7
    with pytest.raises(ValueError):
        FusionParams(candidate_depth=101)  # above MAX_RETRIEVAL_K


def test_list_chunks_is_ordered_and_track_filtered(tmp_path: Path) -> None:
    index, _, _, snapshot = _built(tmp_path)
    chunks = index.list_chunks(snapshot.snapshot_id)
    assert chunks == sorted(chunks, key=lambda c: c.chunk_id)
    mle_only = index.list_chunks(snapshot.snapshot_id, track=CareerTrack.MLE)
    assert mle_only
    mle_doc_id = derive_doc_id("https://example.com/ml-pipelines", _COLLECTED)
    assert {chunk.doc_id for chunk in mle_only} == {mle_doc_id}
