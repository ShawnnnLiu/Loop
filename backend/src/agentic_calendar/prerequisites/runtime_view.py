"""Runtime task view (axiom 11).

The Planner produces ``task_plan`` which contains ``dependencies`` only.
Code computes ``prerequisites_met``, ``blocked_by``, and
``eligible_for_scheduling`` from those dependencies plus the live completion
state. The result is the ``RuntimeTask`` model.

This module is the single place where prerequisite status is computed.
Importing it from validation, scheduler, supervisor, or anywhere else is the
deterministic alternative to letting the LLM mark prerequisites met.
"""

from __future__ import annotations

from collections.abc import Iterable

from pydantic import BaseModel, ConfigDict, Field


class RuntimeTask(BaseModel):
    """Derived runtime view of a single task.

    All fields are computed; nothing here comes directly from the LLM.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    task_id: str
    prerequisites_met: bool
    blocked_by: list[str] = Field(default_factory=list)
    eligible_for_scheduling: bool


def prerequisites_met(
    dependencies: Iterable[str], completed_task_ids: Iterable[str]
) -> bool:
    """Return ``True`` when every dependency is in the completed set.

    This function is the canonical implementation of the contract in
    ``axioms/11-prerequisite-logic.md``::

        def prerequisites_met(task, completed_task_ids):
            return all(dep_id in completed_task_ids for dep_id in task.dependencies)
    """
    completed = set(completed_task_ids)
    return all(dep in completed for dep in dependencies)


def blocked_by(
    dependencies: Iterable[str], completed_task_ids: Iterable[str]
) -> list[str]:
    """Return the dependency IDs that are still not complete, in input order."""
    completed = set(completed_task_ids)
    return [dep for dep in dependencies if dep not in completed]
