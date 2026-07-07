"""``corpus_snapshot`` contract.

Canonical spec: ``docs/specs/corpus-snapshot.schema.md``.

A :class:`CorpusSnapshot` is the pinning unit for eval reproducibility: a
retrieval eval (and later, claim assembly) runs against a ``snapshot_id``,
never against "whatever the corpus is right now". Snapshots are immutable —
a corpus change produces a new snapshot, the same way plan mutations produce
plan versions (axiom 15's discipline applied to evidence).

The snapshot carries its members' ``content_hash``es, so the pin is
self-contained: the contract verifies ``snapshot_id`` against
:func:`derive_snapshot_id` without needing the registry. The registry enforces
the half the contract cannot see — every ``doc_id`` resolves and
``content_hashes[i]`` really belongs to ``doc_ids[i]``.

``chunking_params`` is **part of the snapshot identity** (grounding-RAG G-C):
downstream chunks, retrieval indexes, labels, and metrics are only valid for
one exact chunking configuration, so re-chunking is a new snapshot, never an
in-place change — an eval can never silently run against re-chunked data.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from agentic_calendar.contracts.corpus_document import CONTENT_HASH_PATTERN


class ChunkingParams(BaseModel):
    """The chunking configuration a snapshot's derived chunks are valid for.

    ``target_chars`` is a soft maximum (a chunk closes before the unit that
    would overshoot it; only a single oversized unit is hard-split) and
    ``overlap_chars`` is an upper bound (overlap snaps to unit boundaries).
    Values are heuristic priors — chunk size is an eval ablation, not a tuned
    constant. A change to chunking *behavior* is a new ``algorithm`` value.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    algorithm: Literal["structure_v1"]
    target_chars: int = Field(gt=0)
    overlap_chars: int = Field(ge=0)

    @model_validator(mode="after")
    def _overlap_strictly_below_target(self) -> ChunkingParams:
        if self.overlap_chars >= self.target_chars:
            raise ValueError(
                f"overlap_chars ({self.overlap_chars}) must be strictly less "
                f"than target_chars ({self.target_chars}) — equal overlap "
                "would make chunking non-progressing"
            )
        return self


def chunking_fingerprint(params: ChunkingParams) -> str:
    """Canonical string form of ``params`` for identity derivation."""
    return f"{params.algorithm}:{params.target_chars}:{params.overlap_chars}"


def derive_snapshot_id(
    content_hashes: Iterable[str], chunking_params: ChunkingParams
) -> str:
    """Derive the snapshot identity from member hashes + chunking parameters.

    ``snap_`` + first 16 hex chars of sha256 over the chunking fingerprint
    followed by the sorted, de-duplicated hashes, joined by ``"\\n"`` —
    byte-stable and member-order-independent, so the same document set under
    the same chunking parameters always yields the same id.
    """
    canonical = "\n".join(
        [chunking_fingerprint(chunking_params), *sorted(set(content_hashes))]
    )
    return f"snap_{hashlib.sha256(canonical.encode('utf-8')).hexdigest()[:16]}"


class CorpusSnapshot(BaseModel):
    """One immutable, content-addressed pin of a corpus membership."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    snapshot_id: str = Field(pattern=r"^snap_[0-9a-f]{16}$")
    created_at: datetime
    doc_ids: list[str] = Field(min_length=1)
    content_hashes: list[str] = Field(min_length=1)
    chunking_params: ChunkingParams

    @model_validator(mode="after")
    def _doc_ids_sorted_unique(self) -> CorpusSnapshot:
        if len(set(self.doc_ids)) != len(self.doc_ids):
            raise ValueError("doc_ids contains duplicates")
        if self.doc_ids != sorted(self.doc_ids):
            raise ValueError("doc_ids must be sorted ascending (canonical order)")
        return self

    @model_validator(mode="after")
    def _hashes_parallel_and_well_formed(self) -> CorpusSnapshot:
        if len(self.content_hashes) != len(self.doc_ids):
            raise ValueError(
                f"content_hashes length ({len(self.content_hashes)}) must equal "
                f"doc_ids length ({len(self.doc_ids)})"
            )
        malformed = [h for h in self.content_hashes if not CONTENT_HASH_PATTERN.match(h)]
        if malformed:
            raise ValueError(
                f"content_hashes contains malformed sha256 digests: {malformed}"
            )
        return self

    @model_validator(mode="after")
    def _snapshot_id_matches_derivation(self) -> CorpusSnapshot:
        expected = derive_snapshot_id(self.content_hashes, self.chunking_params)
        if self.snapshot_id != expected:
            raise ValueError(
                f"snapshot_id {self.snapshot_id!r} does not match its derivation "
                f"from content_hashes + chunking_params (expected {expected!r})"
            )
        return self
