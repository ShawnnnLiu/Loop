"""``retrieval_result`` contract.

Canonical spec: ``docs/specs/retrieval-result.schema.md``.

The ranked answer to one :class:`~agentic_calendar.contracts.retrieval_query.RetrievalQuery`
against one pinned corpus snapshot. The envelope names its evidence version
(``snapshot_id``) and embeds the exact query it answered, so downstream
artifacts (claim records, eval reports) are self-describing.

The determinism rule is enforced *by the contract*: ranks are contiguous,
scores are non-increasing, and exact score ties are ordered by ``chunk_id``
ascending — the producing index cannot emit an out-of-order result without
failing validation here. Scores are retriever-relative — BM25 (negated so
higher is better) from the FTS5 index, or reciprocal-rank-fusion mass from
the hybrid retriever — a pure function of query + snapshot (+ the pinned
embedding model for hybrid) either way, and never assigned by an LLM
(axiom 08).
"""

from __future__ import annotations

import re
from itertools import pairwise

from pydantic import BaseModel, ConfigDict, Field, model_validator

from agentic_calendar.contracts.corpus_document import DOC_ID_PATTERN
from agentic_calendar.contracts.retrieval_query import RetrievalQuery

#: ``chunk_`` + first 16 hex chars of the chunker's derivation hash.
CHUNK_ID_PATTERN = re.compile(r"^chunk_[0-9a-f]{16}$")


class RankedChunk(BaseModel):
    """One ranked chunk reference with provenance (text stays in the index)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    rank: int = Field(ge=1)
    chunk_id: str = Field(pattern=CHUNK_ID_PATTERN.pattern)
    doc_id: str = Field(pattern=DOC_ID_PATTERN.pattern)
    ordinal: int = Field(ge=0)
    score: float
    start_char: int = Field(ge=0)
    end_char: int = Field(ge=1)
    breadcrumb: str | None = None

    @model_validator(mode="after")
    def _slice_is_well_formed(self) -> RankedChunk:
        if self.start_char >= self.end_char:
            raise ValueError(
                f"start_char ({self.start_char}) must be strictly less than "
                f"end_char ({self.end_char})"
            )
        return self


class RetrievalResult(BaseModel):
    """One query's ranked chunk references against one pinned snapshot."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    snapshot_id: str = Field(pattern=r"^snap_[0-9a-f]{16}$")
    query: RetrievalQuery
    results: list[RankedChunk] = Field(default_factory=list)

    @model_validator(mode="after")
    def _ranks_contiguous(self) -> RetrievalResult:
        ranks = [entry.rank for entry in self.results]
        if ranks != list(range(1, len(ranks) + 1)):
            raise ValueError(
                f"ranks must be contiguous from 1 in list order, got {ranks}"
            )
        return self

    @model_validator(mode="after")
    def _ordering_matches_tie_break(self) -> RetrievalResult:
        for earlier, later in pairwise(self.results):
            if later.score > earlier.score:
                raise ValueError(
                    "scores must be non-increasing in rank order "
                    f"(rank {earlier.rank} score {earlier.score} < "
                    f"rank {later.rank} score {later.score})"
                )
            if later.score == earlier.score and later.chunk_id <= earlier.chunk_id:
                raise ValueError(
                    "exact score ties must be ordered by chunk_id ascending "
                    f"(ranks {earlier.rank}/{later.rank})"
                )
        return self

    @model_validator(mode="after")
    def _chunk_ids_unique(self) -> RetrievalResult:
        chunk_ids = [entry.chunk_id for entry in self.results]
        if len(set(chunk_ids)) != len(chunk_ids):
            raise ValueError("results contains duplicate chunk_ids")
        return self

    @model_validator(mode="after")
    def _within_query_budget(self) -> RetrievalResult:
        if len(self.results) > self.query.k:
            raise ValueError(
                f"results length ({len(self.results)}) exceeds query.k "
                f"({self.query.k})"
            )
        return self
