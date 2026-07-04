"""Environment-construction test: the disposition store is wired in both backends.

A regression guard for the Phase B3 wiring — ``build_environment`` must
construct a working ``TaskDispositionStore`` whether persistence is in-memory
or the SQLite twin.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from agentic_calendar.app.environment import (
    LlmNodeBundle,
    NodeDependencies,
    build_environment,
)
from agentic_calendar.contracts.reason_codes import ReasonCode
from agentic_calendar.contracts.syllabus_units import SyllabusUnits
from agentic_calendar.contracts.task_disposition import (
    DispositionSource,
    TaskDispositionRecord,
    TaskDispositionType,
)
from agentic_calendar.contracts.task_plan import TaskPlan
from agentic_calendar.disposition.disposition_store import TaskDispositionStore
from agentic_calendar.llm_nodes.planner import FixturePlanner
from agentic_calendar.llm_nodes.reflection_summary import DeterministicReflectionSummary
from agentic_calendar.llm_nodes.strategist import FixtureStrategist
from agentic_calendar.llm_nodes.user_facing_explanation import (
    DeterministicUserFacingExplanation,
)
from tests._fixture_loader import iter_valid

_SYLLABUS = SyllabusUnits.model_validate(next(iter_valid("syllabus_units")).payload)
_PLAN = TaskPlan.model_validate(next(iter_valid("task_plan")).payload)


def _factory(deps: NodeDependencies) -> LlmNodeBundle:
    del deps
    return LlmNodeBundle(
        strategist=FixtureStrategist({"role": _SYLLABUS}),
        planner=FixturePlanner({"v": _PLAN}),
        reflection=DeterministicReflectionSummary(),
        explanation=DeterministicUserFacingExplanation(),
    )


@pytest.mark.parametrize("persist", [False, True])
def test_build_environment_wires_disposition_store(
    tmp_path: Path, persist: bool
) -> None:
    db_path = (tmp_path / "env.db") if persist else None
    env = build_environment(nodes_factory=_factory, db_path=db_path)

    assert isinstance(env.disposition_store, TaskDispositionStore)

    record = TaskDispositionRecord(
        disposition_id="d1",
        user_id="user_1",
        plan_version="plan_1",
        task_id="t1",
        disposition=TaskDispositionType.DROPPED,
        reason_code=ReasonCode.TASK_DROPPED_BY_USER,
        source=DispositionSource.USER,
        created_at=datetime(2026, 6, 24, 19, 0, tzinfo=UTC),
    )
    env.disposition_store.append(record)
    assert env.disposition_store.task_ids_with_disposition(
        "user_1", TaskDispositionType.DROPPED
    ) == {"t1"}
