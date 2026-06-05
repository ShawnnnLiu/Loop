"""``strategist_input`` contract.

Canonical spec: ``docs/specs/syllabus-units.schema.md`` ("Strategist Inputs").

The validated bundle handed to ``StrategistNode``: the user profile, the scored
source claims it may cite, and the strategy constraints it must respect. Assembled
and re-validated at the node boundary so a malformed claim set or constraint set
is caught before generation, not three layers deep.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .source_claim import SourceClaim
from .strategy_constraints import StrategyConstraints
from .user_profile import UserProfile


class StrategistInput(BaseModel):
    """Validated input bundle for the Strategist."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    user_profile: UserProfile
    source_claims: list[SourceClaim] = Field(default_factory=list)
    strategy_constraints: StrategyConstraints = Field(default_factory=StrategyConstraints)

    @model_validator(mode="after")
    def _claim_ids_unique(self) -> StrategistInput:
        ids = [c.claim_id for c in self.source_claims]
        if len(set(ids)) != len(ids):
            dupes = sorted({i for i in ids if ids.count(i) > 1})
            raise ValueError(f"duplicate source_claim claim_id values: {dupes}")
        return self
