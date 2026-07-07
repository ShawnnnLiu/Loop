"""SQLite corpus registry.

Persistent twin of :class:`~agentic_calendar.retrieval.registry.InMemoryCorpusRegistry`:
same :class:`~agentic_calendar.retrieval.registry.CorpusRegistry` protocol,
same typed errors, same invariants. Rows hold the canonical Pydantic JSON dump
plus the document text; reads rebuild the frozen models with
``model_validate_json`` so a round trip is contract-validated, never trusted,
and ``get_text`` re-checks the content hash so corruption fails loudly.

Existence/conflict checks run as explicit SELECTs inside the insert
transaction, so a concurrent register of the same id cannot slip past and the
error stays the typed :class:`CorpusDocumentConflictError`, never a leaked
``sqlite3.IntegrityError`` (same discipline as ``SqliteSourceClaimStore``).
"""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from datetime import datetime

from agentic_calendar.common.sqlite import SqliteDatabase
from agentic_calendar.contracts.career_track import CareerTrack
from agentic_calendar.contracts.corpus_document import CorpusDocument
from agentic_calendar.contracts.corpus_snapshot import ChunkingParams, CorpusSnapshot

from .errors import (
    CorpusDocumentConflictError,
    EmptySnapshotError,
    UnknownCorpusDocumentError,
)
from .registry import _build_snapshot, _checked_text

_SCHEMA_COMPONENT = "retrieval.corpus"
_SCHEMA_VERSION = 1
_SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS corpus_documents (
        doc_id TEXT PRIMARY KEY,
        payload TEXT NOT NULL,
        text TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS corpus_snapshots (
        snapshot_id TEXT PRIMARY KEY,
        payload TEXT NOT NULL
    )
    """,
)


class SqliteCorpusRegistry:
    """Persistent corpus registry. Thread-safe via the shared database lock."""

    def __init__(self, db: SqliteDatabase) -> None:
        self._db = db
        db.ensure_schema(_SCHEMA_COMPONENT, version=_SCHEMA_VERSION, statements=_SCHEMA)

    def register(self, document: CorpusDocument, *, text: str) -> bool:
        checked = _checked_text(document, text)
        with self._db.transaction() as cur:
            row = cur.execute(
                "SELECT payload FROM corpus_documents WHERE doc_id = ?",
                (document.doc_id,),
            ).fetchone()
            if row is not None:
                existing = CorpusDocument.model_validate_json(row[0])
                if existing == document:
                    return False
                raise CorpusDocumentConflictError(document.doc_id)
            cur.execute(
                "INSERT INTO corpus_documents (doc_id, payload, text)"
                " VALUES (?, ?, ?)",
                (document.doc_id, document.model_dump_json(), checked),
            )
            return True

    def get_document(self, doc_id: str) -> CorpusDocument | None:
        with self._db.read() as cur:
            row = cur.execute(
                "SELECT payload FROM corpus_documents WHERE doc_id = ?",
                (doc_id,),
            ).fetchone()
        if row is None:
            return None
        return CorpusDocument.model_validate_json(row[0])

    def get_text(self, doc_id: str) -> str | None:
        with self._db.read() as cur:
            row = cur.execute(
                "SELECT payload, text FROM corpus_documents WHERE doc_id = ?",
                (doc_id,),
            ).fetchone()
        if row is None:
            return None
        document = CorpusDocument.model_validate_json(row[0])
        return _checked_text(document, row[1])

    def list_documents(
        self, *, track: CareerTrack | None = None
    ) -> list[CorpusDocument]:
        # Insertion order (rowid) — the same ordering contract as the
        # in-memory registry's append list. Track filtering happens on the
        # validated models: the corpus is hundreds of documents, not millions.
        with self._db.read() as cur:
            rows = cur.execute(
                "SELECT payload FROM corpus_documents ORDER BY rowid"
            ).fetchall()
        documents = [CorpusDocument.model_validate_json(row[0]) for row in rows]
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
        # Resolution, derivation, and insert share one transaction so a
        # concurrent register/create cannot interleave between them.
        with self._db.transaction() as cur:
            resolve = self._resolve_documents(cur, doc_ids)
            snapshot = _build_snapshot(
                doc_ids,
                created_at=created_at,
                chunking_params=chunking_params,
                resolve=resolve,
            )
            row = cur.execute(
                "SELECT payload FROM corpus_snapshots WHERE snapshot_id = ?",
                (snapshot.snapshot_id,),
            ).fetchone()
            if row is not None:
                return CorpusSnapshot.model_validate_json(row[0])
            cur.execute(
                "INSERT INTO corpus_snapshots (snapshot_id, payload) VALUES (?, ?)",
                (snapshot.snapshot_id, snapshot.model_dump_json()),
            )
            return snapshot

    def get_snapshot(self, snapshot_id: str) -> CorpusSnapshot | None:
        with self._db.read() as cur:
            row = cur.execute(
                "SELECT payload FROM corpus_snapshots WHERE snapshot_id = ?",
                (snapshot_id,),
            ).fetchone()
        if row is None:
            return None
        return CorpusSnapshot.model_validate_json(row[0])

    def list_snapshots(self) -> list[CorpusSnapshot]:
        with self._db.read() as cur:
            rows = cur.execute(
                "SELECT payload FROM corpus_snapshots ORDER BY rowid"
            ).fetchall()
        return [CorpusSnapshot.model_validate_json(row[0]) for row in rows]

    @staticmethod
    def _resolve_documents(
        cur: sqlite3.Cursor, doc_ids: Sequence[str]
    ) -> dict[str, CorpusDocument]:
        requested = sorted(set(doc_ids))
        resolve: dict[str, CorpusDocument] = {}
        for doc_id in requested:
            row = cur.execute(
                "SELECT payload FROM corpus_documents WHERE doc_id = ?",
                (doc_id,),
            ).fetchone()
            if row is not None:
                resolve[doc_id] = CorpusDocument.model_validate_json(row[0])
        missing = [i for i in requested if i not in resolve]
        if missing:
            raise UnknownCorpusDocumentError(missing)
        return resolve
