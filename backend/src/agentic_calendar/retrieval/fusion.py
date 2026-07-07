"""Hybrid retrieval: dense cosine + BM25 under reciprocal rank fusion (G-E).

The hybrid retriever is a **measured ablation**, not the foundation — BM25 is
the shipped v1 posture and stays the CI gate. This module earns its place (or
doesn't) on the G-D labeled query set, hybrid-vs-BM25, same snapshot, table
in the commit message.

Everything here is deterministic plain code over plain data. The embedding
provider never appears: query and chunk vectors come out of the
:class:`~agentic_calendar.retrieval.vectors.SqliteVectorStore` cache, and a
missing vector is the typed
:class:`~agentic_calendar.retrieval.errors.MissingEmbeddingsError` — never a
silent fall-back to BM25-only, which would fake the ablation's own numbers.

Fusion is standard reciprocal rank fusion: each arm contributes
``1 / (rrf_k + rank)`` per chunk it ranks; higher mass is better. Ties break
by ``chunk_id`` ascending — the same rule the ``RetrievalResult`` contract
re-validates on the way out, so hybrid results are byte-identical for the
same (query, snapshot, model, params).
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field

from agentic_calendar.contracts.corpus_document import content_hash_for
from agentic_calendar.contracts.retrieval_query import (
    MAX_RETRIEVAL_K,
    RetrievalQuery,
)
from agentic_calendar.contracts.retrieval_result import RankedChunk, RetrievalResult

from .chunking import Chunk
from .errors import MissingEmbeddingsError
from .index import SqliteChunkIndex
from .vectors import SqliteVectorStore, cosine_similarity

#: Heuristic priors (axiom 08 calibration honesty): the standard RRF constant
#: and a candidate depth comfortably above the eval's k=5 — both recorded on
#: every hybrid result via the params object, neither tuned yet.
DEFAULT_FUSION_PARAMS_RRF_K = 60
DEFAULT_FUSION_PARAMS_DEPTH = 50


class FusionParams(BaseModel):
    """Explicit hybrid-retrieval configuration (recorded, never implicit)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    rrf_k: int = Field(default=DEFAULT_FUSION_PARAMS_RRF_K, ge=1)
    candidate_depth: int = Field(
        default=DEFAULT_FUSION_PARAMS_DEPTH, ge=1, le=MAX_RETRIEVAL_K
    )


def reciprocal_rank_fusion(
    rankings: Sequence[Sequence[str]], *, rrf_k: int
) -> dict[str, float]:
    """Fuse ranked id lists: each arm adds ``1 / (rrf_k + rank)`` per id.

    Pure arithmetic over list positions (1-based); ids absent from an arm
    simply receive no mass from it.
    """
    mass: dict[str, float] = {}
    for ranking in rankings:
        for position, item_id in enumerate(ranking, start=1):
            mass[item_id] = mass.get(item_id, 0.0) + 1.0 / (rrf_k + position)
    return mass


class HybridSearcher:
    """BM25 + dense-cosine hybrid over one vector-cached snapshot.

    Satisfies the same ``search(query, *, snapshot_id)`` surface as
    :class:`~agentic_calendar.retrieval.index.SqliteChunkIndex`, so the
    retrieval eval grades either retriever unchanged (the ablation seam).
    """

    def __init__(
        self,
        index: SqliteChunkIndex,
        vectors: SqliteVectorStore,
        *,
        model_name: str,
        params: FusionParams | None = None,
    ) -> None:
        self._index = index
        self._vectors = vectors
        self._model_name = model_name
        self._params = params if params is not None else FusionParams()

    @property
    def params(self) -> FusionParams:
        return self._params

    def search(self, query: RetrievalQuery, *, snapshot_id: str) -> RetrievalResult:
        chunks = self._index.list_chunks(snapshot_id, track=query.track)
        if not chunks:
            return RetrievalResult(snapshot_id=snapshot_id, query=query, results=[])

        query_vector = self._query_vector(query.query_text)
        chunk_vectors = self._chunk_vectors(chunks)

        # Dense arm: cosine over the full (track-filtered) chunk universe,
        # tie-broken like every ranking here, truncated to candidate depth.
        dense_scored = sorted(
            (
                (cosine_similarity(query_vector, chunk_vectors[chunk.chunk_id]), chunk.chunk_id)
                for chunk in chunks
            ),
            key=lambda pair: (-pair[0], pair[1]),
        )
        dense_arm = [chunk_id for _, chunk_id in dense_scored[: self._params.candidate_depth]]

        # BM25 arm: the existing index ranking at the same candidate depth.
        bm25_result = self._index.search(
            RetrievalQuery(
                query_text=query.query_text,
                track=query.track,
                k=self._params.candidate_depth,
            ),
            snapshot_id=snapshot_id,
        )
        bm25_arm = [entry.chunk_id for entry in bm25_result.results]

        mass = reciprocal_rank_fusion(
            [bm25_arm, dense_arm], rrf_k=self._params.rrf_k
        )
        fused = sorted(mass.items(), key=lambda item: (-item[1], item[0]))

        by_chunk_id = {chunk.chunk_id: chunk for chunk in chunks}
        results = [
            RankedChunk(
                rank=position,
                chunk_id=chunk_id,
                doc_id=by_chunk_id[chunk_id].doc_id,
                ordinal=by_chunk_id[chunk_id].ordinal,
                score=score,
                start_char=by_chunk_id[chunk_id].start_char,
                end_char=by_chunk_id[chunk_id].end_char,
                breadcrumb=by_chunk_id[chunk_id].breadcrumb,
            )
            for position, (chunk_id, score) in enumerate(
                fused[: query.k], start=1
            )
        ]
        return RetrievalResult(snapshot_id=snapshot_id, query=query, results=results)

    def _query_vector(self, query_text: str) -> list[float]:
        content_hash = content_hash_for(query_text)
        vector = self._vectors.get(
            content_hash, model_name=self._model_name, input_type="query"
        )
        if vector is None:
            raise MissingEmbeddingsError(
                model_name=self._model_name,
                input_type="query",
                missing_count=1,
                sample=[content_hash],
            )
        return vector

    def _chunk_vectors(self, chunks: Sequence[Chunk]) -> dict[str, list[float]]:
        """Every chunk's cached vector, keyed by ``chunk_id``. All or raise."""
        hash_by_chunk = {
            chunk.chunk_id: content_hash_for(chunk.text) for chunk in chunks
        }
        cached = self._vectors.get_many(
            list(hash_by_chunk.values()),
            model_name=self._model_name,
            input_type="document",
        )
        missing = sorted(
            content_hash
            for content_hash in hash_by_chunk.values()
            if content_hash not in cached
        )
        if missing:
            raise MissingEmbeddingsError(
                model_name=self._model_name,
                input_type="document",
                missing_count=len(missing),
                sample=missing[:3],
            )
        return {
            chunk_id: cached[content_hash]
            for chunk_id, content_hash in hash_by_chunk.items()
        }
