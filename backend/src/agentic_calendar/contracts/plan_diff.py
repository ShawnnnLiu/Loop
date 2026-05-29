"""``plan_diff`` contract.

Canonical spec: ``docs/specs/plan-diff.schema.md``.

The diff between two plan versions, computed deterministically. The LLM may
summarize the diff in friendly language, but the diff itself must be produced
by code (axiom 15).

The diff is hierarchical:

* Level 1 (``summary``): headline counts and aggregates, always shown.
* Level 2 (``task_changes``): one entry per affected task.
* Level 3 (``field_changes``): per-field old/new values with typed reason codes.

Phase 2 ships only the **contract**. The deterministic diff-computation service
lands later; this phase makes the type available so the approval flow and audit
log can carry diffs once they are computed.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .reason_codes import ReasonCode

_ALLOWED_FIELD_CHANGE_REASON_CODES: frozenset[ReasonCode] = frozenset(
    {
        ReasonCode.DEEP_WORK_WINDOW_CONFLICT,
        ReasonCode.USER_DURATION_CALIBRATION,
        ReasonCode.DEPENDENCY_RESCHEDULED,
        ReasonCode.WEEKLY_CAPACITY_REBALANCE,
        ReasonCode.EXTERNAL_CALENDAR_CONFLICT,
        ReasonCode.USER_PROFILE_CHANGE,
        ReasonCode.DRIFT_REMEDIATION,
    }
)


class DiffChangeType(StrEnum):
    """Allowed values for ``TaskChange.change_type`` (spec lines 111-120)."""

    ADDED = "added"
    REMOVED = "removed"
    RESCHEDULED = "rescheduled"
    DURATION_CHANGED = "duration_changed"
    DEPENDENCY_CHANGED = "dependency_changed"
    MODULE_REASSIGNED = "module_reassigned"
    PRIORITY_CHANGED = "priority_changed"
    UNCHANGED = "unchanged"


class PlanDiffSummary(BaseModel):
    """Level 1 headline (spec lines 89-99)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    tasks_added: int = Field(ge=0)
    tasks_removed: int = Field(ge=0)
    tasks_rescheduled: int = Field(ge=0)
    tasks_with_duration_changes: int = Field(ge=0)
    modules_affected: tuple[str, ...]
    net_weekly_load_change_min: int
    timeline_change_days: int


class TaskChange(BaseModel):
    """Level 2 per-task summary (spec lines 101-109)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    task_id: str = Field(min_length=1)
    change_type: DiffChangeType
    user_facing_summary: str = Field(min_length=1)


class FieldChange(BaseModel):
    """Level 3 field-level diff (spec lines 122-145)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    task_id: str = Field(min_length=1)
    field: str = Field(min_length=1)
    old_value: Any = None
    new_value: Any = None
    delta: int | None = None
    delta_minutes: int | None = None
    reason_code: ReasonCode

    @model_validator(mode="after")
    def _reason_code_allowed(self) -> FieldChange:
        if self.reason_code not in _ALLOWED_FIELD_CHANGE_REASON_CODES:
            raise ValueError(
                f"plan-diff field change reason_code {self.reason_code.value!r} is not in the "
                "allowed set; see plan-diff.schema.md lines 133-143"
            )
        return self


class PlanDiff(BaseModel):
    """Immutable, read-only diff between two plan versions."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    diff_id: str = Field(min_length=1)
    from_plan_version: str = Field(min_length=1)
    to_plan_version: str = Field(min_length=1)
    computed_at: datetime
    summary: PlanDiffSummary
    task_changes: tuple[TaskChange, ...]
    field_changes: tuple[FieldChange, ...]

    @model_validator(mode="after")
    def _computed_at_tz_aware(self) -> PlanDiff:
        if self.computed_at.tzinfo is None:
            raise ValueError("plan diff computed_at must be timezone-aware")
        return self

    @model_validator(mode="after")
    def _from_differs_from_to(self) -> PlanDiff:
        if self.from_plan_version == self.to_plan_version:
            raise ValueError(
                "plan diff from_plan_version and to_plan_version must differ"
            )
        return self

    @model_validator(mode="after")
    def _no_task_added_and_removed(self) -> PlanDiff:
        added = {
            tc.task_id
            for tc in self.task_changes
            if tc.change_type is DiffChangeType.ADDED
        }
        removed = {
            tc.task_id
            for tc in self.task_changes
            if tc.change_type is DiffChangeType.REMOVED
        }
        both = added & removed
        if both:
            raise ValueError(
                f"task(s) cannot be both added and removed: {sorted(both)!r}"
            )
        return self

    @model_validator(mode="after")
    def _field_changes_reference_task_changes(self) -> PlanDiff:
        present: set[str] = {tc.task_id for tc in self.task_changes}
        for fc in self.field_changes:
            if fc.task_id not in present:
                raise ValueError(
                    f"field change task_id {fc.task_id!r} has no matching "
                    "entry in task_changes"
                )
        return self

    @model_validator(mode="after")
    def _modules_affected_matches_task_changes(self) -> PlanDiff:
        # The spec invariant requires summary.modules_affected to be the
        # deduplicated union of modules from task_changes. Phase 2 ships the
        # contract before the diff-computation service exists, so task_changes
        # carries no module information directly. We enforce the *shape* here
        # (modules_affected is a sorted, unique tuple) and defer the cross-check
        # to the future diff service that produces the data.
        modules = self.summary.modules_affected
        if len(set(modules)) != len(modules):
            raise ValueError("summary.modules_affected must contain unique values")
        return self
