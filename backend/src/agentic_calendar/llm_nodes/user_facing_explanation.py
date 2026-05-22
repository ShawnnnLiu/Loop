"""User-facing-explanation node — deterministic Phase 1 implementation.

This node turns a deterministic outcome into user-readable text, without
introducing any new source of truth.

In Phase 1 we only explain ``ValidationResult``. The translations themselves
are a static, reviewable mapping in :mod:`agentic_calendar.contracts.translations`
(``ViolationType`` -> message). Keeping this deterministic ensures:

- the same typed violations always produce the same explanation (replayable),
- tests can assert on results without relying on prompt wording,
- "user-facing copy" does not become an LLM-controlled control plane.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from agentic_calendar.contracts.translations import user_facing
from agentic_calendar.contracts.validation_result import ValidationResult


class UserExplanation(BaseModel):
    """The structured wrapper for user-visible copy."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    summary: str = Field(min_length=1)
    detail: list[str] = Field(default_factory=list)


class DeterministicUserFacingExplanation:
    """Composes a short user-readable summary from a validation result."""

    def run(
        self, *, run_id: str, validation_result: ValidationResult
    ) -> UserExplanation:
        del run_id
        if validation_result.valid:
            return UserExplanation(
                summary="Plan looks good.",
                detail=[],
            )
        details = [user_facing(v.type) for v in validation_result.violations]
        unique_details = list(dict.fromkeys(details))  # de-dupe, preserve order
        summary = "Re-running with fixes."
        return UserExplanation(summary=summary, detail=unique_details)
