"""Retrieval region — corpus registry (grounding layer, axiom 08).

Versioned evidence, not a scrape pile: every corpus document enters with
provenance, license, and track metadata, its text pinned by a content hash;
snapshots are the immutable pinning unit retrieval evals run against. Later
increments add chunking and the FTS5 retriever on top of this registry.

Allowed dependencies (enforced by ``backend/.importlinter``): ``common``,
``contracts``. Notably **not** ``source_claims`` — claim assembly composes the
two kernels from outside the region set, keeping them siblings, not
dependents. Corpus text is public-web content only; user data never enters
the corpus.
"""

from __future__ import annotations

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
    "CorpusContentHashMismatchError",
    "CorpusDocumentConflictError",
    "CorpusRegistry",
    "CorpusRegistryError",
    "EmptySnapshotError",
    "InMemoryCorpusRegistry",
    "SqliteCorpusRegistry",
    "UnknownCorpusDocumentError",
    "html_to_text",
    "looks_like_html",
    "normalize_fetched_text",
    "normalize_text",
]
