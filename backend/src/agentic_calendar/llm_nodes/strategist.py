"""Strategist node — fixture-backed fake (Phase 1).

The Strategist's job is to turn a user profile into a structured
``SyllabusUnits`` proposal. In Phase 1 we replay a pre-baked fixture so the
deterministic core can be exercised end-to-end without an LLM SDK. Phase 5
swaps the implementation; the public surface stays the same.
"""

from __future__ import annotations

from collections.abc import Mapping

from agentic_calendar.contracts.syllabus_units import SyllabusUnits
from agentic_calendar.contracts.user_profile import UserProfile

from .base import LLMNodeError


class FixtureStrategist:
    """Fake Strategist that returns one of a fixed set of canned outputs.

    The fixture chosen is keyed off ``user_profile.target_role`` (extensible
    by passing a richer ``key`` callable). The returned object is always
    re-validated by the ``SyllabusUnits`` contract before it leaves this
    method, so a malformed fixture is caught here and not three layers deep.
    """

    def __init__(self, fixtures: Mapping[str, SyllabusUnits]) -> None:
        if not fixtures:
            raise ValueError("FixtureStrategist requires at least one fixture")
        self._fixtures = dict(fixtures)

    def run(self, *, run_id: str, user_profile: UserProfile) -> SyllabusUnits:
        # Accepted for protocol parity; not used by the deterministic fake.
        del run_id
        key = user_profile.target_role
        if key not in self._fixtures:
            raise LLMNodeError(
                f"FixtureStrategist has no fixture for target_role={key!r}; "
                f"known keys: {sorted(self._fixtures)}"
            )
        # Re-validate at the boundary: callers should only ever receive objects
        # that satisfy the contract, even if fixtures were mutated in-memory.
        return SyllabusUnits.model_validate(self._fixtures[key].model_dump())
