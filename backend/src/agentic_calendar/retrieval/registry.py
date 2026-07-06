"""Corpus registry: the only writer of corpus documents and snapshots.

Stores each registered document's normalized text next to its
:class:`~agentic_calendar.contracts.corpus_document.CorpusDocument` metadata
record, and creates/loads immutable
:class:`~agentic_calendar.contracts.corpus_snapshot.CorpusSnapshot` pins
(axiom 08, corpus-registry subsection).

Invariants enforced here (the half the contracts cannot see):

* stored text really hashes to ``content_hash`` — checked on register **and**
  on read, so corruption fails loudly instead of serving wrong evidence;
* registered documents are immutable — the same ``doc_id`` with different
  content or metadata is a typed conflict, never an overwrite;
* re-registering an identical document is a no-op (hash-idempotent
  re-ingest, so the ingestion CLI can re-run on unchanged pages);
* snapshot members must resolve to registered documents, and recreating an
  existing membership returns the stored snapshot (original ``created_at``
  preserved) — same-membership-same-identity, by derivation.

There is deliberately no delete or update surface: a corpus change is a new
fetch (new ``doc_id``) and a new snapshot, mirroring plan-version discipline.
"""

from __future__ import annotations

import threading
from collections.abc import Sequence
from datetime import datetime
from typing import Protocol, runtime_checkable

from agentic_calendar.contracts.career_track import CareerTrack
from agentic_calendar.contracts.corpus_document import CorpusDocument, content_hash_for
from agentic_calendar.contracts.corpus_snapshot import (
    ChunkingParams,
    CorpusSnapshot,
    derive_snapshot_id,
)

from .errors import (
    CorpusContentHashMismatchError,
    CorpusDocumentConflictError,
    EmptySnapshotError,
    UnknownCorpusDocumentError,
)


@runtime_checkable
class CorpusRegistry(Protocol):
    """Register/read surface for corpus documents and snapshots."""

    def register(self, document: CorpusDocument, *, text: str) -> bool:
        """Store ``document`` with its normalized ``text``.

        Returns ``True`` when newly registered, ``False`` on an identical
        re-register (no-op). Raises a typed error on hash mismatch or on a
        conflicting re-register.
        """
        ...

    def get_document(self, doc_id: str) -> CorpusDocument | None: ...

    def get_text(self, doc_id: str) -> str | None: ...

    def list_documents(
        self, *, track: CareerTrack | None = None
    ) -> list[CorpusDocument]: ...

    def create_snapshot(
        self,
        doc_ids: Sequence[str],
        *,
        created_at: datetime,
        chunking_params: ChunkingParams,
    ) -> CorpusSnapshot: ...

    def get_snapshot(self, snapshot_id: str) -> CorpusSnapshot | None: ...

    def list_snapshots(self) -> list[CorpusSnapshot]: ...


def _checked_text(document: CorpusDocument, text: str) -> str:
    """Return ``text`` if it hashes to the document's pin; typed raise if not."""
    actual = content_hash_for(text)
    if actual != document.content_hash:
        raise CorpusContentHashMismatchError(
            document.doc_id, expected=document.content_hash, actual=actual
        )
    return text


def _build_snapshot(
    doc_ids: Sequence[str],
    *,
    created_at: datetime,
    chunking_params: ChunkingParams,
    resolve: dict[str, CorpusDocument],
) -> CorpusSnapshot:
    """Canonicalize membership and derive the snapshot from resolved documents.

    ``resolve`` must contain every requested id (the caller checks and raises
    :class:`UnknownCorpusDocumentError` first, store-appropriately).
    """
    canonical_ids = sorted(set(doc_ids))
    hashes = [resolve[doc_id].content_hash for doc_id in canonical_ids]
    return CorpusSnapshot(
        snapshot_id=derive_snapshot_id(hashes, chunking_params),
        created_at=created_at,
        doc_ids=canonical_ids,
        content_hashes=hashes,
        chunking_params=chunking_params,
    )


class InMemoryCorpusRegistry:
    """Ephemeral twin of the SQLite registry. Thread-safe, non-persistent."""

    def __init__(self) -> None:
        self._documents: dict[str, CorpusDocument] = {}
        self._texts: dict[str, str] = {}
        self._doc_order: list[str] = []
        self._snapshots: dict[str, CorpusSnapshot] = {}
        self._snapshot_order: list[str] = []
        self._lock = threading.RLock()

    def register(self, document: CorpusDocument, *, text: str) -> bool:
        checked = _checked_text(document, text)
        with self._lock:
            existing = self._documents.get(document.doc_id)
            if existing is not None:
                if existing == document:
                    return False
                raise CorpusDocumentConflictError(document.doc_id)
            self._documents[document.doc_id] = document
            self._texts[document.doc_id] = checked
            self._doc_order.append(document.doc_id)
            return True

    def get_document(self, doc_id: str) -> CorpusDocument | None:
        with self._lock:
            return self._documents.get(doc_id)

    def get_text(self, doc_id: str) -> str | None:
        with self._lock:
            document = self._documents.get(doc_id)
            if document is None:
                return None
            return _checked_text(document, self._texts[doc_id])

    def list_documents(
        self, *, track: CareerTrack | None = None
    ) -> list[CorpusDocument]:
        with self._lock:
            documents = [self._documents[i] for i in self._doc_order]
        if track is None:
            return documents
        return [d for d in documents if track in d.track_tags]

    def create_snapshot(
        self,
        doc_ids: Sequence[str],
        *,
        created_at: datetime,
        chunking_params: ChunkingParams,
    ) -> CorpusSnapshot:
        if not doc_ids:
            raise EmptySnapshotError()
        with self._lock:
            missing = sorted({i for i in doc_ids if i not in self._documents})
            if missing:
                raise UnknownCorpusDocumentError(missing)
            snapshot = _build_snapshot(
                doc_ids,
                created_at=created_at,
                chunking_params=chunking_params,
                resolve=self._documents,
            )
            existing = self._snapshots.get(snapshot.snapshot_id)
            if existing is not None:
                return existing
            self._snapshots[snapshot.snapshot_id] = snapshot
            self._snapshot_order.append(snapshot.snapshot_id)
            return snapshot

    def get_snapshot(self, snapshot_id: str) -> CorpusSnapshot | None:
        with self._lock:
            return self._snapshots.get(snapshot_id)

    def list_snapshots(self) -> list[CorpusSnapshot]:
        with self._lock:
            return [self._snapshots[i] for i in self._snapshot_order]
