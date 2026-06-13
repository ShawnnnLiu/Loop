"""Planner node — fixture-backed fake (Phase 1).

The Planner's job is to turn a ``SyllabusUnits`` into a ``TaskPlan``. The
fake here looks up a canned plan keyed by ``syllabus_version``. As with the
Strategist, the returned object is re-validated by the contract before it
leaves the method.
"""

from __future__ import annotations

from collections.abc import Mapping

from agentic_calendar.contracts.syllabus_units import SyllabusUnits
from agentic_calendar.contracts.task_plan import TaskPlan
from agentic_calendar.contracts.user_profile import UserProfile
from agentic_calendar.contracts.validation_result import ValidationResult

from .base import LLMNodeError


class FixturePlanner:
    """Fake Planner. Look up canned ``TaskPlan`` by ``syllabus_version``."""

    def __init__(self, fixtures: Mapping[str, TaskPlan]) -> None:
        if not fixtures:
            raise ValueError("FixturePlanner requires at least one fixture")
        self._fixtures = dict(fixtures)

    def run(
        self,
        *,
        run_id: str,
        syllabus: SyllabusUnits,
        user_profile: UserProfile | None = None,
        repair: ValidationResult | None = None,
    ) -> TaskPlan:
        """Return the canned plan for ``syllabus.syllabus_version``.

        ``user_profile`` and ``repair`` exist for protocol parity with
        ``AnthropicPlanner`` (the real adapter embeds the profile's scheduling
        constraints and the failed ``ValidationResult`` in its prompt). Canned
        output cannot honor either, so both are accepted and ignored.
        """
        del run_id, user_profile, repair
        key = syllabus.syllabus_version
        if key not in self._fixtures:
            raise LLMNodeError(
                f"FixturePlanner has no fixture for syllabus_version={key!r}; "
                f"known keys: {sorted(self._fixtures)}"
            )
        # Re-validate at the boundary: callers should only ever receive objects
        # that satisfy the contract, even if fixtures were mutated in-memory.
        return TaskPlan.model_validate(self._fixtures[key].model_dump())
