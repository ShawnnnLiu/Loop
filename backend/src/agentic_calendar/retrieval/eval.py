"""Retrieval eval: labeled query sets and rank metrics (grounding-RAG G-D).

There is no LLM anywhere in the retrieval path, so this eval is a pure
function over checked-in data — queries + labels + a pinned snapshot — and
may gate CI directly (amended axiom 22: gating splits by determinism, and
this side is fully deterministic). Metric functions mirror the Tier-1 style
of ``llm_nodes/eval.py``: tiny, hand-checkable arithmetic, tested against
hand-computed fixtures.

Labels are **doc-level** (a chunk hit counts if its parent document is
relevant — chunk-level labeling is not worth the labeling cost in v1) and
reference documents by ``source_url``: URLs are the stable, human-auditable
name a labeler works with, and they resolve deterministically against the
pinned snapshot's membership at eval time. A label URL the snapshot does not
contain is a typed error, never a silent zero.

Metric floors are heuristic priors seeded from the first measured run
(axiom 08 calibration honesty applies to them too).
"""

from __future__ import annotations

import json
import math
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from agentic_calendar.common.errors import AgenticCalendarError
from agentic_calendar.contracts.career_track import CareerTrack
from agentic_calendar.contracts.corpus_document import CorpusDocument
from agentic_calendar.contracts.corpus_snapshot import CorpusSnapshot
from agentic_calendar.contracts.retrieval_query import RetrievalQuery
from agentic_calendar.contracts.retrieval_result import RetrievalResult

from .registry import CorpusRegistry


class RetrievalEvalError(AgenticCalendarError):
    """A query set, label, or recording is unusable; never a silent skip."""


@runtime_checkable
class ChunkSearcher(Protocol):
    """Any deterministic retriever the eval can grade (the ablation seam).

    ``SqliteChunkIndex`` (BM25) and ``HybridSearcher`` (G-E) both satisfy
    this; the eval grades whichever it is handed, so hybrid-vs-BM25 is two
    runs of the same grading code over the same labels.
    """

    def search(self, query: RetrievalQuery, *, snapshot_id: str) -> RetrievalResult: ...


# --------------------------------------------------------------------------- #
# Labeled query set (evalsets/retrieval_queries_v*.json; append-only,
# versioned like the LLM eval sets).
# --------------------------------------------------------------------------- #


class RetrievalQueryCase(BaseModel):
    """One labeled query: text, track scope, and the relevant documents."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    query_id: str = Field(pattern=r"^rq_[a-z0-9_]+$")
    query_text: str = Field(min_length=1)
    track: CareerTrack | None = None
    relevant_source_urls: list[str] = Field(min_length=1)
    notes: str | None = None

    @model_validator(mode="after")
    def _relevant_urls_unique(self) -> RetrievalQueryCase:
        if len(set(self.relevant_source_urls)) != len(self.relevant_source_urls):
            raise ValueError("relevant_source_urls contains duplicates")
        return self


class RetrievalQuerySet(BaseModel):
    """The checked-in labeled set. Append-only across versions."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    query_set_version: str = Field(min_length=1)
    comment: str | None = None
    cases: list[RetrievalQueryCase] = Field(min_length=1)

    @model_validator(mode="after")
    def _query_ids_unique(self) -> RetrievalQuerySet:
        ids = [case.query_id for case in self.cases]
        duplicates = sorted({i for i in ids if ids.count(i) > 1})
        if duplicates:
            raise ValueError(f"duplicate query_ids: {duplicates}")
        return self


def load_query_set(path: Path) -> RetrievalQuerySet:
    """Load and validate a labeled query set (typed raise on invalid)."""
    try:
        payload = json.loads(path.read_text("utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RetrievalEvalError(f"unreadable query set {path}: {exc}") from exc
    try:
        return RetrievalQuerySet.model_validate(payload)
    except ValidationError as exc:
        raise RetrievalEvalError(f"invalid query set {path}: {exc}") from exc


def resolve_relevant_doc_ids(
    case: RetrievalQueryCase, documents: Sequence[CorpusDocument]
) -> frozenset[str]:
    """Resolve a case's label URLs against the pinned snapshot's members.

    Doc ids embed the collection date, so labels name the stable
    ``source_url`` instead and resolve here. Unknown URLs are a typed error:
    a label that silently matched nothing would fake a zero into recall.
    """
    by_url: dict[str, list[str]] = {}
    for document in documents:
        by_url.setdefault(document.source_url, []).append(document.doc_id)
    missing = [u for u in case.relevant_source_urls if u not in by_url]
    if missing:
        raise RetrievalEvalError(
            f"case {case.query_id!r} labels source_urls the snapshot does not "
            f"contain: {missing}"
        )
    return frozenset(
        doc_id for url in case.relevant_source_urls for doc_id in by_url[url]
    )


# --------------------------------------------------------------------------- #
# Rank metrics — pure functions, doc-level, binary relevance.
# --------------------------------------------------------------------------- #


def ranked_doc_ids(result: RetrievalResult) -> list[str]:
    """Chunk ranking → doc ranking by first occurrence (labels are doc-level)."""
    return list(dict.fromkeys(entry.doc_id for entry in result.results))


def recall_at_k(ranked_docs: Sequence[str], relevant: frozenset[str], k: int) -> float:
    """Fraction of relevant documents present in the top ``k``."""
    if not relevant:
        raise RetrievalEvalError("recall is undefined with no relevant documents")
    return len(set(ranked_docs[:k]) & relevant) / len(relevant)


def reciprocal_rank(ranked_docs: Sequence[str], relevant: frozenset[str]) -> float:
    """1 / rank of the first relevant document; 0.0 on a total miss."""
    for position, doc_id in enumerate(ranked_docs, start=1):
        if doc_id in relevant:
            return 1.0 / position
    return 0.0


def ndcg_at_k(ranked_docs: Sequence[str], relevant: frozenset[str], k: int) -> float:
    """Binary-gain nDCG@k: DCG over the ranking / DCG of the ideal ranking."""
    if not relevant:
        raise RetrievalEvalError("nDCG is undefined with no relevant documents")
    dcg = sum(
        1.0 / math.log2(position + 1)
        for position, doc_id in enumerate(ranked_docs[:k], start=1)
        if doc_id in relevant
    )
    ideal = sum(
        1.0 / math.log2(position + 1)
        for position in range(1, min(len(relevant), k) + 1)
    )
    return dcg / ideal


# --------------------------------------------------------------------------- #
# Per-case + aggregate report.
# --------------------------------------------------------------------------- #


class CaseMetrics(BaseModel):
    """One case's measured metrics (rounded for stable serialization)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    query_id: str
    relevant_count: int = Field(ge=1)
    retrieved_doc_ids: list[str]
    first_relevant_rank: int | None
    recall_at_k: float = Field(ge=0.0, le=1.0)
    reciprocal_rank: float = Field(ge=0.0, le=1.0)
    ndcg_at_k: float = Field(ge=0.0, le=1.0)


class RetrievalReport(BaseModel):
    """Aggregate retrieval metrics against one pinned snapshot."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    query_set_version: str
    snapshot_id: str
    k: int = Field(ge=1)
    cases: int = Field(ge=1)
    mean_recall_at_k: float = Field(ge=0.0, le=1.0)
    mean_reciprocal_rank: float = Field(ge=0.0, le=1.0)
    mean_ndcg_at_k: float = Field(ge=0.0, le=1.0)
    per_case: list[CaseMetrics]


def grade_case(
    case: RetrievalQueryCase,
    result: RetrievalResult,
    documents: Sequence[CorpusDocument],
    *,
    k: int,
) -> CaseMetrics:
    """Grade one search result against one labeled case. Pure."""
    relevant = resolve_relevant_doc_ids(case, documents)
    ranked = ranked_doc_ids(result)
    first_hit = next(
        (position for position, d in enumerate(ranked, start=1) if d in relevant),
        None,
    )
    return CaseMetrics(
        query_id=case.query_id,
        relevant_count=len(relevant),
        retrieved_doc_ids=ranked,
        first_relevant_rank=first_hit,
        recall_at_k=round(recall_at_k(ranked, relevant, k), 4),
        reciprocal_rank=round(reciprocal_rank(ranked, relevant), 4),
        ndcg_at_k=round(ndcg_at_k(ranked, relevant, k), 4),
    )


def evaluate_query_set(
    query_set: RetrievalQuerySet,
    *,
    searcher: ChunkSearcher,
    registry: CorpusRegistry,
    snapshot: CorpusSnapshot,
    k: int,
) -> RetrievalReport:
    """Run every case against one retriever for ``snapshot`` and aggregate.

    Deterministic end to end: the retriever's determinism rule plus pure
    metric arithmetic. Every case is graded — a case that cannot resolve its
    labels raises rather than being skipped.
    """
    documents = [d for d in (registry.get_document(i) for i in snapshot.doc_ids) if d]
    if len(documents) != len(snapshot.doc_ids):
        raise RetrievalEvalError(
            "registry no longer resolves every snapshot member; the corpus "
            "database does not match the pinned snapshot"
        )
    per_case = []
    for case in query_set.cases:
        query = RetrievalQuery(query_text=case.query_text, track=case.track, k=k)
        result = searcher.search(query, snapshot_id=snapshot.snapshot_id)
        per_case.append(grade_case(case, result, documents, k=k))
    count = len(per_case)
    return RetrievalReport(
        query_set_version=query_set.query_set_version,
        snapshot_id=snapshot.snapshot_id,
        k=k,
        cases=count,
        mean_recall_at_k=round(sum(c.recall_at_k for c in per_case) / count, 4),
        mean_reciprocal_rank=round(
            sum(c.reciprocal_rank for c in per_case) / count, 4
        ),
        mean_ndcg_at_k=round(sum(c.ndcg_at_k for c in per_case) / count, 4),
        per_case=per_case,
    )


# --------------------------------------------------------------------------- #
# Floors (heuristic priors until calibrated — seeded from the first measured
# run, mirroring the eval-gate threshold style).
# --------------------------------------------------------------------------- #


class RetrievalFloors(BaseModel):
    """Merge-gate floors on the aggregate metrics."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    min_mean_recall_at_k: float = Field(ge=0.0, le=1.0)
    min_mean_reciprocal_rank: float = Field(ge=0.0, le=1.0)
    min_mean_ndcg_at_k: float = Field(ge=0.0, le=1.0)


def floor_breaches(report: RetrievalReport, floors: RetrievalFloors) -> list[str]:
    """Deterministic breach descriptions; empty when within floors."""
    breaches: list[str] = []
    checks = (
        ("mean_recall_at_k", report.mean_recall_at_k, floors.min_mean_recall_at_k),
        (
            "mean_reciprocal_rank",
            report.mean_reciprocal_rank,
            floors.min_mean_reciprocal_rank,
        ),
        ("mean_ndcg_at_k", report.mean_ndcg_at_k, floors.min_mean_ndcg_at_k),
    )
    for name, measured, floor in checks:
        if measured < floor:
            breaches.append(
                f"{name} {measured:.4f} is below the floor {floor:.4f} "
                "(seeded from the first measured run; heuristic prior)"
            )
    return breaches
