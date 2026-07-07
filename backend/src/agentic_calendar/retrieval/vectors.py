"""Chunk-embedding vector cache + pure cosine ranking (grounding-RAG G-E).

Vectors are **plain data** to this region: the embedding provider transport
lives in ``llm_nodes/`` (the only region allowed to integrate model-provider
APIs) and the two are composed from ``tools/`` — ``retrieval/`` never learns
how a vector was produced, only that it is cached here under the content
hash of the exact text it embeds.

Cache identity is ``(content_hash, model_name, input_type)``:

* ``content_hash`` — :func:`~agentic_calendar.contracts.corpus_document.content_hash_for`
  of the embedded text (the repo's single hash definition), so identical
  chunk text across snapshots reuses its vector and a re-chunk that changes
  text is a cache miss, never a stale hit.
* ``model_name`` — vectors from different models are never comparable.
* ``input_type`` — the provider embeds documents and queries under different
  retrieval prompts, so the same text embeds to different vectors per type.

Writes are first-write-pins (``INSERT OR IGNORE``): re-embedding the same
text under the same identity is a no-op, which is what "embed once per chunk
per model" means operationally. Vectors are packed float32 — the round trip
through the blob is exact for provider floats and keeps 564 chunks around
2 MB; brute-force cosine over that is milliseconds (scope guard: no vector
database).
"""

from __future__ import annotations

import math
from array import array
from collections.abc import Iterable, Sequence

from agentic_calendar.common.sqlite import SqliteDatabase

_SCHEMA_COMPONENT = "retrieval.vectors"
_SCHEMA_VERSION = 1
_SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS retrieval_embeddings (
        content_hash TEXT NOT NULL,
        model_name TEXT NOT NULL,
        input_type TEXT NOT NULL,
        dimension INTEGER NOT NULL,
        vector BLOB NOT NULL,
        PRIMARY KEY (content_hash, model_name, input_type)
    )
    """,
)


def pack_vector(vector: Sequence[float]) -> bytes:
    """Pack to little-endian float32 bytes (deterministic storage form)."""
    packed = array("f", vector)
    return packed.tobytes()


def unpack_vector(blob: bytes, *, dimension: int) -> list[float]:
    """Unpack float32 bytes; a length mismatch is corruption and raises."""
    unpacked = array("f")
    unpacked.frombytes(blob)
    if len(unpacked) != dimension:
        raise ValueError(
            f"vector blob holds {len(unpacked)} floats but dimension is "
            f"{dimension}"
        )
    return list(unpacked)


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    """Pure cosine similarity; 0.0 for a zero-norm side (honest no-signal)."""
    if len(a) != len(b):
        raise ValueError(f"dimension mismatch: {len(a)} vs {len(b)}")
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


class SqliteVectorStore:
    """The embedding cache over the shared corpus database.

    Like the FTS index this is derived data — losing it costs one re-embed
    run, never evidence — but unlike the index it is *not* rebuildable
    offline, so the embed CLI treats every miss as networked work behind the
    ask-first gate.
    """

    def __init__(self, db: SqliteDatabase) -> None:
        self._db = db
        db.ensure_schema(_SCHEMA_COMPONENT, version=_SCHEMA_VERSION, statements=_SCHEMA)

    def put_many(
        self,
        entries: Iterable[tuple[str, Sequence[float]]],
        *,
        model_name: str,
        input_type: str,
    ) -> int:
        """Cache ``(content_hash, vector)`` pairs. First write pins.

        Returns how many rows were newly written (re-writes of an existing
        identity are ignored, keeping the first-cached vector authoritative).
        """
        written = 0
        with self._db.transaction() as cur:
            for content_hash, vector in entries:
                cur.execute(
                    "INSERT OR IGNORE INTO retrieval_embeddings"
                    " (content_hash, model_name, input_type, dimension, vector)"
                    " VALUES (?, ?, ?, ?, ?)",
                    (
                        content_hash,
                        model_name,
                        input_type,
                        len(vector),
                        pack_vector(vector),
                    ),
                )
                written += cur.rowcount
        return written

    def get(
        self, content_hash: str, *, model_name: str, input_type: str
    ) -> list[float] | None:
        with self._db.read() as cur:
            row = cur.execute(
                "SELECT dimension, vector FROM retrieval_embeddings"
                " WHERE content_hash = ? AND model_name = ? AND input_type = ?",
                (content_hash, model_name, input_type),
            ).fetchone()
        if row is None:
            return None
        return unpack_vector(row[1], dimension=row[0])

    def get_many(
        self, content_hashes: Sequence[str], *, model_name: str, input_type: str
    ) -> dict[str, list[float]]:
        """Resolve every cached hash; absent hashes are simply not in the map."""
        found: dict[str, list[float]] = {}
        with self._db.read() as cur:
            for content_hash in dict.fromkeys(content_hashes):
                row = cur.execute(
                    "SELECT dimension, vector FROM retrieval_embeddings"
                    " WHERE content_hash = ? AND model_name = ? AND input_type = ?",
                    (content_hash, model_name, input_type),
                ).fetchone()
                if row is not None:
                    found[content_hash] = unpack_vector(row[1], dimension=row[0])
        return found

    def missing(
        self, content_hashes: Sequence[str], *, model_name: str, input_type: str
    ) -> list[str]:
        """Hashes with no cached vector, first-seen order, de-duplicated."""
        cached = self.get_many(content_hashes, model_name=model_name, input_type=input_type)
        return [h for h in dict.fromkeys(content_hashes) if h not in cached]

    def count(self, *, model_name: str) -> int:
        with self._db.read() as cur:
            row = cur.execute(
                "SELECT COUNT(*) FROM retrieval_embeddings WHERE model_name = ?",
                (model_name,),
            ).fetchone()
        return int(row[0])
