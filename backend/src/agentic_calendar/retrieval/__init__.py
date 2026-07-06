"""Retrieval region — corpus registry + chunking (grounding layer, axiom 08).

Versioned evidence, not a scrape pile: every corpus document enters with
provenance, license, and track metadata, its text pinned by a content hash;
snapshots are the immutable pinning unit retrieval evals run against, and
they pin the chunking parameters too — chunks are a pure function of a
snapshot. Later increments add the FTS5 retriever on top.

Allowed dependencies (enforced by ``backend/.importlinter``): ``common``,
``contracts``. Notably **not** ``source_claims`` — claim assembly composes the
two kernels from outside the region set, keeping them siblings, not
dependents. Corpus text is public-web content only; user data never enters
the corpus.
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
    UnknownCorpusDocumentError,
)
from .normalize import (
    html_to_text,
    looks_like_html,
    normalize_fetched_text,
    normalize_text,
)
from .registry import CorpusRegistry, InMemoryCorpusRegistry
from .sqlite_registry import SqliteCorpusRegistry

__all__ = [
    "CHUNK_ID_PATTERN",
    "DEFAULT_CHUNKING_PARAMS",
    "Chunk",
    "CorpusContentHashMismatchError",
    "CorpusDocumentConflictError",
    "CorpusRegistry",
    "CorpusRegistryError",
    "EmptySnapshotError",
    "InMemoryCorpusRegistry",
    "SqliteCorpusRegistry",
    "UnknownCorpusDocumentError",
    "chunk_snapshot",
    "chunk_text",
    "derive_chunk_id",
    "html_to_text",
    "looks_like_html",
    "normalize_fetched_text",
    "normalize_text",
]
