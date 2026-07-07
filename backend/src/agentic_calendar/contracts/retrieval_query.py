"""``retrieval_query`` contract.

Canonical spec: ``docs/specs/retrieval-query.schema.md``.

One typed request against the chunk index of a pinned corpus snapshot:
query text, an optional :class:`~agentic_calendar.contracts.career_track.CareerTrack`
filter, and a result budget. There is no LLM anywhere in the retrieval path —
the index compiles ``query_text`` to an FTS5 match expression
deterministically, so the same query against the same snapshot always
produces byte-identical results (``retrieval_result``'s determinism rule).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from agentic_calendar.contracts.career_track import CareerTrack

#: Scope guard, not pagination: retrieval serves claim assembly and evals.
MAX_RETRIEVAL_K = 100


class RetrievalQuery(BaseModel):
    """One deterministic retrieval request against a pinned snapshot."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    query_text: str = Field(min_length=1)
    track: CareerTrack | None = None
    k: int = Field(ge=1, le=MAX_RETRIEVAL_K)
