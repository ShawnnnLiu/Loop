"""Tests for retrieval eval metrics — hand-computed arithmetic fixtures.

Every expected value below is worked out by hand (the Tier-1 grader test
convention): recall@k is a set intersection over the top-k, RR is 1/rank of
the first hit, and nDCG uses binary gains with log2 discounts.
"""

from __future__ import annotations

import math
from datetime import date

import pytest

from agentic_calendar.contracts.career_track import CareerTrack
from agentic_calendar.contracts.corpus_document import (
    CorpusDocument,
    content_hash_for,
    derive_doc_id,
)
from agentic_calendar.contracts.retrieval_query import RetrievalQuery
from agentic_calendar.contracts.retrieval_result import RankedChunk, RetrievalResult
from agentic_calendar.contracts.source_claim import SourceType
from agentic_calendar.retrieval.eval import (
    RetrievalEvalError,
    RetrievalFloors,
    RetrievalQueryCase,
    RetrievalQuerySet,
    floor_breaches,
    grade_case,
    ndcg_at_k,
    ranked_doc_ids,
    recall_at_k,
    reciprocal_rank,
    resolve_relevant_doc_ids,
)

_A, _B, _C, _D = "doc_" + "a" * 16, "doc_" + "b" * 16, "doc_" + "c" * 16, "doc_" + "d" * 16
_RELEVANT = frozenset({_A, _C})
_RANKED = [_A, _B, _C, _D]


def test_recall_at_k_hand_computed() -> None:
    # top-2 = {A, B}; relevant = {A, C}; intersection = {A} -> 1/2.
    assert recall_at_k(_RANKED, _RELEVANT, 2) == 0.5
    # top-4 contains both -> 2/2.
    assert recall_at_k(_RANKED, _RELEVANT, 4) == 1.0
    assert recall_at_k([_B, _D], _RELEVANT, 2) == 0.0
    # More relevant docs than k: recall@1 with 3 relevant = 1/3.
    assert recall_at_k([_A], frozenset({_A, _B, _C}), 1) == pytest.approx(1 / 3)


def test_reciprocal_rank_hand_computed() -> None:
    assert reciprocal_rank(_RANKED, _RELEVANT) == 1.0  # A at rank 1
    assert reciprocal_rank([_B, _A], _RELEVANT) == 0.5  # first hit at rank 2
    assert reciprocal_rank([_B, _D], _RELEVANT) == 0.0  # total miss


def test_ndcg_at_k_hand_computed() -> None:
    # Hits at ranks 1 and 3: DCG = 1/log2(2) + 1/log2(4) = 1 + 0.5 = 1.5.
    # Ideal with 2 relevant in top-3: 1/log2(2) + 1/log2(3) = 1.63093.
    expected = 1.5 / (1.0 + 1.0 / math.log2(3))
    assert ndcg_at_k(_RANKED, _RELEVANT, 3) == pytest.approx(expected)
    # Perfect single hit at k=1 with 3 relevant docs: DCG = IDCG@1 = 1.
    assert ndcg_at_k([_A], frozenset({_A, _B, _C}), 1) == 1.0
    assert ndcg_at_k([_B, _D], _RELEVANT, 2) == 0.0


def test_metrics_reject_empty_relevant_set() -> None:
    with pytest.raises(RetrievalEvalError):
        recall_at_k(_RANKED, frozenset(), 2)
    with pytest.raises(RetrievalEvalError):
        ndcg_at_k(_RANKED, frozenset(), 2)


def _entry(rank: int, doc_id: str, score: float) -> RankedChunk:
    return RankedChunk(
        rank=rank,
        chunk_id=f"chunk_{rank:016x}",
        doc_id=doc_id,
        ordinal=0,
        score=score,
        start_char=0,
        end_char=10,
    )


def test_ranked_doc_ids_dedupes_by_first_occurrence() -> None:
    result = RetrievalResult(
        snapshot_id="snap_7d3a91c04b5e2f68",
        query=RetrievalQuery(query_text="q", k=5),
        results=[
            _entry(1, _A, 3.0),
            _entry(2, _B, 2.0),
            _entry(3, _A, 1.5),
            _entry(4, _C, 1.0),
        ],
    )
    assert ranked_doc_ids(result) == [_A, _B, _C]


# --------------------------------------------------------------------------- #
# Label resolution + case grading.
# --------------------------------------------------------------------------- #

_COLLECTED = date(2026, 7, 6)


def _doc(url: str) -> CorpusDocument:
    return CorpusDocument(
        doc_id=derive_doc_id(url, _COLLECTED),
        source_url=url,
        source_type=SourceType.UNCLASSIFIED,
        license_note="Public page; test fixture.",
        date_collected=_COLLECTED,
        track_tags=[CareerTrack.SWE],
        content_hash=content_hash_for(url),
        title=url,
    )


def test_resolve_relevant_doc_ids_by_url() -> None:
    docs = [_doc("https://example.com/a"), _doc("https://example.com/b")]
    case = RetrievalQueryCase(
        query_id="rq_swe_001",
        query_text="q",
        track=CareerTrack.SWE,
        relevant_source_urls=["https://example.com/b"],
    )
    assert resolve_relevant_doc_ids(case, docs) == frozenset({docs[1].doc_id})


def test_unresolvable_label_url_is_typed_not_silent() -> None:
    case = RetrievalQueryCase(
        query_id="rq_swe_001",
        query_text="q",
        relevant_source_urls=["https://example.com/vanished"],
    )
    with pytest.raises(RetrievalEvalError, match="vanished"):
        resolve_relevant_doc_ids(case, [_doc("https://example.com/a")])


def test_grade_case_assembles_hand_computed_metrics() -> None:
    docs = [_doc("https://example.com/a"), _doc("https://example.com/b")]
    case = RetrievalQueryCase(
        query_id="rq_swe_001",
        query_text="q",
        relevant_source_urls=["https://example.com/a"],
    )
    result = RetrievalResult(
        snapshot_id="snap_7d3a91c04b5e2f68",
        query=RetrievalQuery(query_text="q", k=2),
        results=[_entry(1, docs[1].doc_id, 2.0), _entry(2, docs[0].doc_id, 1.0)],
    )
    metrics = grade_case(case, result, docs, k=2)
    assert metrics.first_relevant_rank == 2
    assert metrics.recall_at_k == 1.0
    assert metrics.reciprocal_rank == 0.5
    # Hit at rank 2: DCG = 1/log2(3); IDCG@2 with 1 relevant = 1.
    assert metrics.ndcg_at_k == round(1.0 / math.log2(3), 4)


def test_query_set_rejects_duplicate_ids() -> None:
    case = {
        "query_id": "rq_dup",
        "query_text": "q",
        "relevant_source_urls": ["https://example.com/a"],
    }
    with pytest.raises(ValueError, match="duplicate query_ids"):
        RetrievalQuerySet(query_set_version="v1", cases=[case, case])  # type: ignore[list-item]


def test_floor_breaches_name_each_metric() -> None:
    report_floors = RetrievalFloors(
        min_mean_recall_at_k=0.9,
        min_mean_reciprocal_rank=0.5,
        min_mean_ndcg_at_k=0.8,
    )
    from agentic_calendar.retrieval.eval import RetrievalReport

    report = RetrievalReport(
        query_set_version="v1",
        snapshot_id="snap_7d3a91c04b5e2f68",
        k=5,
        cases=1,
        mean_recall_at_k=0.8,
        mean_reciprocal_rank=0.6,
        mean_ndcg_at_k=0.7,
        per_case=[
            {
                "query_id": "rq_x",
                "relevant_count": 1,
                "retrieved_doc_ids": [],
                "first_relevant_rank": None,
                "recall_at_k": 0.8,
                "reciprocal_rank": 0.6,
                "ndcg_at_k": 0.7,
            }  # type: ignore[list-item]
        ],
    )
    breaches = floor_breaches(report, report_floors)
    assert len(breaches) == 2
    assert any("mean_recall_at_k" in b for b in breaches)
    assert any("mean_ndcg_at_k" in b for b in breaches)
    assert not any("mean_reciprocal_rank" in b for b in breaches)
