"""``task_plan`` contract.

Canonical spec: ``docs/specs/task-plan.schema.md``.

Output of ``PlannerNode``. The two cross-cutting rules enforced *here* (other
graph / coverage / user-fit checks live in the Validation Layer):

1. ``task_plan`` must **not** carry ``prerequisites_met``. That field is a
   forbidden shortcut: prerequisite status is computed deterministically from
   ``dependencies`` + completion state (axiom 11).
2. ``task_id`` values within a single plan must be unique.

Pydantic ``extra="forbid"`` rejects any unknown field; we additionally
attach an explicit, named validator for ``prerequisites_met`` so the error
message points the LLM (or producer) to the correct axiom rather than a
generic "extra fields not permitted".
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .common_types import FocusLevel, TaskCategory


class Task(BaseModel):
    """One concrete task derived from a syllabus module."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    task_id: str = Field(min_length=1)
    module_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str = ""
    dependencies: list[str] = Field(default_factory=list)
    estimated_duration_min: int = Field(gt=0)
    cognitive_load: int = Field(ge=1, le=5)
    category: TaskCategory
    required_focus_level: FocusLevel
    splittable: bool = False

    @model_validator(mode="after")
    def _no_self_dependency(self) -> Task:
        if self.task_id in self.dependencies:
            raise ValueError(
                f"task {self.task_id!r} declares itself as its own dependency"
            )
        return self


class TaskPlan(BaseModel):
    """A versioned set of tasks (see spec).

    Note: per axiom 11, ``prerequisites_met`` is *not* a field on this model.
    The model rejects it explicitly with ``FORBIDDEN_FIELD_PRESENT`` semantics
    via the ``_reject_prerequisites_met`` validator.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    plan_version: str = Field(min_length=1)
    tasks: list[Task] = Field(min_length=1)

    @model_validator(mode="before")
    @classmethod
    def _reject_prerequisites_met(cls, data: Any) -> Any:
        """Surface ``prerequisites_met`` violations with a precise message.

        ``extra="forbid"`` would already reject it as an unknown field, but
        this validator runs first and produces an axiom-aware error.
        """
        if not isinstance(data, dict):
            return data
        for i, raw_task in enumerate(data.get("tasks") or []):
            if isinstance(raw_task, dict) and "prerequisites_met" in raw_task:
                tid = raw_task.get("task_id", f"<index {i}>")
                raise ValueError(
                    f"task {tid!r} contains forbidden field 'prerequisites_met'; "
                    "compute prerequisite status deterministically (axiom 11)"
                )
        return data

    @model_validator(mode="after")
    def _task_ids_unique(self) -> TaskPlan:
        seen: set[str] = set()
        dupes: list[str] = []
        for t in self.tasks:
            if t.task_id in seen:
                dupes.append(t.task_id)
            seen.add(t.task_id)
        if dupes:
            raise ValueError(f"duplicate task_id values: {sorted(set(dupes))}")
        return self
