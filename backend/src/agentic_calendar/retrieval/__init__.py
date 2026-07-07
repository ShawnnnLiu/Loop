"""Retrieval region — corpus registry + chunking (grounding layer, axiom 08).

Versioned evidence, not a scrape pile: every corpus document enters with
provenance, license, and track metadata, its text pinned by a content hash;
snapshots are the immutable pinning unit retrieval evals run against, and
they pin the chunking parameters too — chunks are a pure function of a
snapshot. The FTS5 index (G-D) is the shipped BM25 retriever; the vector
cache + hybrid fusion (G-E) is a measured ablation over it — vectors enter
this region as plain cached data, never as a provider call.

Allowed dependencies (enforced by ``backend/.importlinter``): ``common``,
``contracts``. Notably **not** ``source_claims`` — claim assembly composes the
two kernels from outside the region set, keeping them siblings, not
dependents — and **not** ``llm_nodes``: the embedding transport lives there
and the two are composed from ``tools/``. Corpus text is public-web content
only; user data never enters the corpus.
"""

from __future__ import annotations

from .chunking import (
    CHUNK_ID_PATTERN,
    DEFAULT_CHUNKING_PARAMS,
    Chunk,
    chunk_snapshot,
    chunk_text,
    derive_chunk_id,
)
from .errors import (
    CorpusContentHashMismatchError,
    CorpusDocumentConflictError,
    CorpusRegistryError,
    EmptySnapshotError,
    Fts5UnavailableError,
    MissingEmbeddingsError,
    RetrievalIndexError,
    SnapshotNotIndexedError,
    UnknownCorpusDocumentError,
)
from .fusion import FusionParams, HybridSearcher, reciprocal_rank_fusion
from .index import SqliteChunkIndex, compile_match_expression, fts5_available
from .normalize import (
    html_to_text,
    looks_like_html,
    normalize_fetched_text,
    normalize_text,
)
from .registry import CorpusRegistry, InMemoryCorpusRegistry
from .sqlite_registry import SqliteCorpusRegistry
from .vectors import SqliteVectorStore, cosine_similarity

__all__ = [
    "CHUNK_ID_PATTERN",
    "DEFAULT_CHUNKING_PARAMS",
    "Chunk",
    "CorpusContentHashMismatchError",
    "CorpusDocumentConflictError",
    "CorpusRegistry",
    "CorpusRegistryError",
    "EmptySnapshotError",
    "Fts5UnavailableError",
    "FusionParams",
    "HybridSearcher",
    "InMemoryCorpusRegistry",
    "MissingEmbeddingsError",
    "RetrievalIndexError",
    "SnapshotNotIndexedError",
    "SqliteChunkIndex",
    "SqliteCorpusRegistry",
    "SqliteVectorStore",
    "UnknownCorpusDocumentError",
    "chunk_snapshot",
    "chunk_text",
    "compile_match_expression",
    "cosine_similarity",
    "derive_chunk_id",
    "fts5_available",
    "html_to_text",
    "looks_like_html",
    "normalize_fetched_text",
    "normalize_text",
    "reciprocal_rank_fusion",
]
