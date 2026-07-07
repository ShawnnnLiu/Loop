"""Typed errors for the retrieval region (axiom 16: no raw exceptions cross)."""

from __future__ import annotations

from agentic_calendar.common.errors import AgenticCalendarError


class CorpusRegistryError(AgenticCalendarError):
    """Base for corpus-registry errors that callers may catch."""


class CorpusContentHashMismatchError(CorpusRegistryError):
    """Document text does not hash to the declared ``content_hash``.

    Raised on register (the caller's text/metadata disagree) and on read
    (stored text no longer matches its pin — corruption, which must fail
    loudly rather than serve silently-wrong evidence).
    """

    def __init__(self, doc_id: str, *, expected: str, actual: str) -> None:
        self.doc_id = doc_id
        self.expected = expected
        self.actual = actual
        super().__init__(
            f"content hash mismatch for {doc_id!r}: declared {expected!r} "
            f"but text hashes to {actual!r}"
        )


class CorpusDocumentConflictError(CorpusRegistryError):
    """A ``doc_id`` is already registered with different content or metadata.

    Registered documents are immutable: a changed page is a new fetch on a new
    ``date_collected`` (hence a new ``doc_id``), never an in-place update.
    """

    def __init__(self, doc_id: str) -> None:
        self.doc_id = doc_id
        super().__init__(
            f"document {doc_id!r} is already registered with different "
            "content or metadata; registered documents are immutable"
        )


class UnknownCorpusDocumentError(CorpusRegistryError):
    """A snapshot referenced ``doc_id``s that are not registered."""

    def __init__(self, doc_ids: list[str]) -> None:
        self.doc_ids = doc_ids
        super().__init__(f"unknown corpus document ids: {doc_ids}")


class EmptySnapshotError(CorpusRegistryError):
    """A snapshot must pin at least one document."""

    def __init__(self) -> None:
        super().__init__("a corpus snapshot must pin at least one document")


class RetrievalIndexError(AgenticCalendarError):
    """Base for chunk-index errors that callers may catch."""


class Fts5UnavailableError(RetrievalIndexError):
    """The linked SQLite build has no FTS5 extension.

    A typed setup error, never a silent fallback: retrieval quality metrics
    are meaningless if some environment quietly served a different ranking.
    Almost every stdlib build ships FTS5; CI verifies it once.
    """

    def __init__(self) -> None:
        super().__init__(
            "this SQLite build lacks the FTS5 extension required by the "
            "retrieval index (verify with: python -c \"import sqlite3; "
            "sqlite3.connect(':memory:').execute('CREATE VIRTUAL TABLE t "
            "USING fts5(x)')\")"
        )


class SnapshotNotIndexedError(RetrievalIndexError):
    """A search targeted a snapshot whose index was never built."""

    def __init__(self, snapshot_id: str) -> None:
        self.snapshot_id = snapshot_id
        super().__init__(
            f"snapshot {snapshot_id!r} has no built chunk index; run "
            "SqliteChunkIndex.build(...) for it first"
        )


class MissingEmbeddingsError(RetrievalIndexError):
    """Hybrid retrieval needs vectors the cache does not hold.

    A typed setup error, never a silent fall-back to BM25-only: an ablation
    that quietly served a different retriever would fake its own numbers.
    The fix is one (ask-first, networked) embed CLI run.
    """

    def __init__(
        self,
        *,
        model_name: str,
        input_type: str,
        missing_count: int,
        sample: list[str],
    ) -> None:
        self.model_name = model_name
        self.input_type = input_type
        self.missing_count = missing_count
        self.sample = sample
        super().__init__(
            f"{missing_count} {input_type} embedding(s) for model "
            f"{model_name!r} are not cached (e.g. {sample}); run "
            "python -m agentic_calendar.tools.embed_corpus to populate the "
            "vector cache first"
        )
