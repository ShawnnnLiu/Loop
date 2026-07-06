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
