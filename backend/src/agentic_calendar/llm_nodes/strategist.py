"""Strategist node — fixture-backed fake (Phase 1, input surface from Phase 5).

The Strategist's job is to turn a user profile (plus scored source claims and
strategy constraints) into a structured ``SyllabusUnits`` proposal. The output
is still replayed from a pre-baked fixture so the deterministic core can be
exercised end-to-end without an LLM SDK — but the *input surface* is real
(Phase 5): the node accepts ``source_claims`` and ``strategy_constraints``,
validates them as a ``StrategistInput`` bundle at the boundary, and gates its
canned output against the constraints. Phase 8 swaps the implementation behind a
real SDK; the public surface stays the same.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from agentic_calendar.contracts.source_claim import SourceClaim
from agentic_calendar.contracts.strategist_input import StrategistInput
from agentic_calendar.contracts.strategy_constraints import StrategyConstraints
from agentic_calendar.contracts.syllabus_units import SyllabusUnits
from agentic_calendar.contracts.user_profile import UserProfile

from .base import LLMNodeError


class FixtureStrategist:
    """Fake Strategist that returns one of a fixed set of canned outputs.

    The fixture chosen is keyed off ``user_profile.target_role``. The returned
    object is always re-validated by the ``SyllabusUnits`` contract before it
    leaves this method, and (when ``enforce_constraints`` is set, the default) is
    checked against the supplied ``strategy_constraints`` so the input surface
    actually gates the output — a malformed or constraint-violating fixture is
    caught here, not three layers deep.
    """

    def __init__(
        self,
        fixtures: Mapping[str, SyllabusUnits],
        *,
        enforce_constraints: bool = True,
    ) -> None:
        if not fixtures:
            raise ValueError("FixtureStrategist requires at least one fixture")
        self._fixtures = dict(fixtures)
        self._enforce_constraints = enforce_constraints

    def run(
        self,
        *,
        run_id: str,
        user_profile: UserProfile,
        source_claims: Sequence[SourceClaim] = (),
        strategy_constraints: StrategyConstraints | None = None,
    ) -> SyllabusUnits:
        # Accepted for protocol parity; not used by the deterministic fake.
        del run_id
        # Assemble + validate the input bundle at the boundary so a malformed
        # claim set / constraint set is rejected before generation.
        bundle = StrategistInput(
            user_profile=user_profile,
            source_claims=list(source_claims),
            strategy_constraints=strategy_constraints or StrategyConstraints(),
        )

        key = bundle.user_profile.target_role
        if key not in self._fixtures:
            raise LLMNodeError(
                f"FixtureStrategist has no fixture for target_role={key!r}; "
                f"known keys: {sorted(self._fixtures)}"
            )

        # Re-validate at the boundary: callers should only ever receive objects
        # that satisfy the contract, even if fixtures were mutated in-memory.
        syllabus = SyllabusUnits.model_validate(self._fixtures[key].model_dump())

        if self._enforce_constraints:
            _check_against_constraints(syllabus, bundle.strategy_constraints)

        return syllabus


def _check_against_constraints(
    syllabus: SyllabusUnits, constraints: StrategyConstraints
) -> None:
    """Raise ``LLMNodeError`` if the canned output violates the cheap constraints.

    Only constraints checkable against a fixture without external state: module
    count, allowed priority values, total estimated minutes, and the
    company-specific-module claim rule. Orphan / expired claim resolution is the
    syllabus validator's job (it needs the claim registry), not duplicated here.
    """
    if len(syllabus.modules) > constraints.max_modules:
        raise LLMNodeError(
            f"syllabus has {len(syllabus.modules)} modules, exceeds "
            f"max_modules={constraints.max_modules}"
        )

    allowed_priorities = set(constraints.required_priority_values)
    disallowed = sorted(
        {
            m.priority.value
            for m in syllabus.modules
            if m.priority not in allowed_priorities
        }
    )
    if disallowed:
        raise LLMNodeError(
            f"syllabus uses priority values {disallowed} not in "
            f"required_priority_values="
            f"{sorted(p.value for p in allowed_priorities)}"
        )

    total_min = sum(m.estimated_total_min for m in syllabus.modules)
    if total_min > constraints.max_total_estimated_minutes:
        raise LLMNodeError(
            f"syllabus total {total_min} min exceeds "
            f"max_total_estimated_minutes={constraints.max_total_estimated_minutes}"
        )

    if constraints.must_reference_claims_for_company_specific_modules:
        offending = [
            m.module_id
            for m in syllabus.modules
            if m.company_specific and not m.source_claim_ids
        ]
        if offending:
            raise LLMNodeError(
                "company-specific modules without source_claim_ids: "
                f"{sorted(offending)}"
            )
