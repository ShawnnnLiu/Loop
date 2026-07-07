"""SQLite FTS5 chunk index — the BM25 retriever (grounding-RAG G-D).

One FTS5 virtual table **per snapshot**: BM25 ranking depends on corpus-wide
term statistics, so sharing one table across snapshots would let an unrelated
ingestion silently shift another snapshot's scores. With a dedicated table,
results are a pure function of (query, snapshot) — same query + same snapshot
is byte-identical, asserted by test.

FTS5 is feature-detected at construction and a missing extension is the typed
:class:`~agentic_calendar.retrieval.errors.Fts5UnavailableError`, never a
silent fallback to a different ranking.

Determinism rule (enforced again by the ``RetrievalResult`` contract on the
way out): ties break by score descending then ``chunk_id`` ascending. Query
text compiles to a bag-of-words OR expression deterministically — no LLM
anywhere in the retrieval path (axiom 08).
"""

from __future__ import annotations

import re
import sqlite3

from agentic_calendar.common.sqlite import SqliteDatabase
from agentic_calendar.contracts.career_track import CareerTrack
from agentic_calendar.contracts.corpus_snapshot import CorpusSnapshot
from agentic_calendar.contracts.retrieval_query import RetrievalQuery
from agentic_calendar.contracts.retrieval_result import RankedChunk, RetrievalResult

from .chunking import Chunk, chunk_snapshot
from .errors import Fts5UnavailableError, SnapshotNotIndexedError
from .registry import CorpusRegistry

_SCHEMA_COMPONENT = "retrieval.index"
_SCHEMA_VERSION = 1
_SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS retrieval_chunks (
        snapshot_id TEXT NOT NULL,
        chunk_id TEXT NOT NULL,
        doc_id TEXT NOT NULL,
        ordinal INTEGER NOT NULL,
        start_char INTEGER NOT NULL,
        end_char INTEGER NOT NULL,
        breadcrumb TEXT,
        track_tags TEXT NOT NULL,
        text TEXT NOT NULL,
        PRIMARY KEY (snapshot_id, chunk_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS retrieval_index_builds (
        snapshot_id TEXT PRIMARY KEY,
        chunk_count INTEGER NOT NULL
    )
    """,
)

_SNAPSHOT_ID = re.compile(r"^snap_([0-9a-f]{16})$")

_WORD = re.compile(r"\w+", re.UNICODE)


def fts5_available() -> bool:
    """Probe the linked SQLite library for FTS5 (side-effect free)."""
    probe = sqlite3.connect(":memory:")
    try:
        probe.execute("CREATE VIRTUAL TABLE probe USING fts5(x)")
    except sqlite3.OperationalError:
        return False
    finally:
        probe.close()
    return True


def compile_match_expression(query_text: str) -> str:
    """Deterministic bag-of-words FTS5 expression (heuristic prior).

    Word tokens are lowercased, double-quoted (so FTS5 operators in user text
    are literals, never syntax), and OR-joined — standard BM25 bag-of-words
    semantics. Text with no word tokens compiles to ``""`` and the caller
    returns an honest empty result.
    """
    tokens = _WORD.findall(query_text.lower())
    return " OR ".join(f'"{token}"' for token in tokens)


def _fts_table_name(snapshot_id: str) -> str:
    """Per-snapshot FTS table name; the id is validated before embedding."""
    match = _SNAPSHOT_ID.match(snapshot_id)
    if match is None:
        raise ValueError(f"malformed snapshot_id: {snapshot_id!r}")
    return f"retrieval_fts_{match.group(1)}"


class SqliteChunkIndex:
    """Per-snapshot BM25 chunk index over the shared SQLite database.

    This is derived data, not a store: rebuilding from the registry is always
    possible, so there is no in-memory twin — FTS5 *is* the implementation.
    """

    def __init__(self, db: SqliteDatabase) -> None:
        if not fts5_available():
            raise Fts5UnavailableError()
        self._db = db
        db.ensure_schema(_SCHEMA_COMPONENT, version=_SCHEMA_VERSION, statements=_SCHEMA)

    def build(self, registry: CorpusRegistry, snapshot: CorpusSnapshot) -> int:
        """Chunk ``snapshot``'s members and index them. Idempotent.

        Returns the chunk count. Re-building an already-built snapshot is a
        no-op returning the stored count (the snapshot is immutable, so the
        derivation cannot have changed).
        """
        fts_table = _fts_table_name(snapshot.snapshot_id)
        # All registry reads happen before the write transaction opens (the
        # shared-database contract: never nest cursors inside a transaction —
        # the registry may live on this same database).
        chunks = chunk_snapshot(registry, snapshot)
        track_tags_by_doc = {
            doc_id: self._track_tags_marker(registry, doc_id)
            for doc_id in snapshot.doc_ids
        }
        with self._db.transaction() as cur:
            row = cur.execute(
                "SELECT chunk_count FROM retrieval_index_builds"
                " WHERE snapshot_id = ?",
                (snapshot.snapshot_id,),
            ).fetchone()
            if row is not None:
                return int(row[0])
            cur.execute(
                f"CREATE VIRTUAL TABLE IF NOT EXISTS {fts_table} USING fts5(text)"
            )
            for chunk in chunks:
                cur.execute(
                    "INSERT INTO retrieval_chunks (snapshot_id, chunk_id, doc_id,"
                    " ordinal, start_char, end_char, breadcrumb, track_tags, text)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        snapshot.snapshot_id,
                        chunk.chunk_id,
                        chunk.doc_id,
                        chunk.ordinal,
                        chunk.start_char,
                        chunk.end_char,
                        chunk.breadcrumb,
                        track_tags_by_doc[chunk.doc_id],
                        chunk.text,
                    ),
                )
                cur.execute(
                    f"INSERT INTO {fts_table} (rowid, text) VALUES (?, ?)",
                    (cur.lastrowid, chunk.text),
                )
            cur.execute(
                "INSERT INTO retrieval_index_builds (snapshot_id, chunk_count)"
                " VALUES (?, ?)",
                (snapshot.snapshot_id, len(chunks)),
            )
            return len(chunks)

    def is_built(self, snapshot_id: str) -> bool:
        with self._db.read() as cur:
            row = cur.execute(
                "SELECT 1 FROM retrieval_index_builds WHERE snapshot_id = ?",
                (snapshot_id,),
            ).fetchone()
        return row is not None

    def search(self, query: RetrievalQuery, *, snapshot_id: str) -> RetrievalResult:
        """Rank chunks for ``query`` against one built snapshot.

        Pure and deterministic; the returned envelope re-validates the
        ordering rule through the ``RetrievalResult`` contract.
        """
        fts_table = _fts_table_name(snapshot_id)
        if not self.is_built(snapshot_id):
            raise SnapshotNotIndexedError(snapshot_id)
        match = compile_match_expression(query.query_text)
        if not match:
            return RetrievalResult(snapshot_id=snapshot_id, query=query, results=[])
        sql = (
            "SELECT c.chunk_id, c.doc_id, c.ordinal, c.start_char, c.end_char,"
            f" c.breadcrumb, -bm25({fts_table}) AS score"
            f" FROM {fts_table} f"
            " JOIN retrieval_chunks c ON c.rowid = f.rowid"
            f" WHERE {fts_table} MATCH ? AND c.snapshot_id = ?"
        )
        parameters: list[object] = [match, snapshot_id]
        if query.track is not None:
            sql += " AND instr(c.track_tags, ?) > 0"
            parameters.append(f",{query.track.value},")
        sql += " ORDER BY score DESC, c.chunk_id ASC LIMIT ?"
        parameters.append(query.k)
        with self._db.read() as cur:
            rows = cur.execute(sql, parameters).fetchall()
        return RetrievalResult(
            snapshot_id=snapshot_id,
            query=query,
            results=[
                RankedChunk(
                    rank=position,
                    chunk_id=row[0],
                    doc_id=row[1],
                    ordinal=row[2],
                    score=row[6],
                    start_char=row[3],
                    end_char=row[4],
                    breadcrumb=row[5],
                )
                for position, row in enumerate(rows, start=1)
            ],
        )

    def list_chunks(
        self, snapshot_id: str, *, track: CareerTrack | None = None
    ) -> list[Chunk]:
        """Every indexed chunk of one built snapshot, ``chunk_id`` ascending.

        The dense arm of hybrid retrieval (G-E) ranks over this listing, so
        it applies the same track filter as :meth:`search` — the two arms
        must always see the same candidate universe.
        """
        if not self.is_built(snapshot_id):
            raise SnapshotNotIndexedError(snapshot_id)
        sql = (
            "SELECT chunk_id, doc_id, ordinal, text, start_char, end_char,"
            " breadcrumb FROM retrieval_chunks WHERE snapshot_id = ?"
        )
        parameters: list[object] = [snapshot_id]
        if track is not None:
            sql += " AND instr(track_tags, ?) > 0"
            parameters.append(f",{track.value},")
        sql += " ORDER BY chunk_id ASC"
        with self._db.read() as cur:
            rows = cur.execute(sql, parameters).fetchall()
        return [
            Chunk(
                chunk_id=row[0],
                doc_id=row[1],
                ordinal=row[2],
                text=row[3],
                start_char=row[4],
                end_char=row[5],
                breadcrumb=row[6],
            )
            for row in rows
        ]

    def get_chunk(self, snapshot_id: str, chunk_id: str) -> Chunk | None:
        """Resolve a ranked reference back to its full chunk (claim assembly)."""
        with self._db.read() as cur:
            row = cur.execute(
                "SELECT chunk_id, doc_id, ordinal, text, start_char, end_char,"
                " breadcrumb FROM retrieval_chunks"
                " WHERE snapshot_id = ? AND chunk_id = ?",
                (snapshot_id, chunk_id),
            ).fetchone()
        if row is None:
            return None
        return Chunk(
            chunk_id=row[0],
            doc_id=row[1],
            ordinal=row[2],
            text=row[3],
            start_char=row[4],
            end_char=row[5],
            breadcrumb=row[6],
        )

    @staticmethod
    def _track_tags_marker(registry: CorpusRegistry, doc_id: str) -> str:
        """Delimited marker string for deterministic track filtering."""
        document = registry.get_document(doc_id)
        # chunk_snapshot resolved every member already; a vanished document
        # mid-build would be registry corruption, which fails loudly there.
        assert document is not None
        return "," + ",".join(tag.value for tag in document.track_tags) + ","
