# 11: Deterministic Prerequisite Logic

## Purpose

Prerequisite logic determines whether a task is eligible for scheduling or execution. It is a deterministic function of task dependencies and completion state. It is not a creative judgment.

The Planner may propose `dependencies`. Code computes `prerequisites_met`.

## Forbidden

`task_plan` must not include `prerequisites_met`. Validation rejects any task plan that contains it. See `../specs/task-plan.schema.md`.

## Function

```python
def prerequisites_met(task, completed_task_ids):
    return all(dep_id in completed_task_ids for dep_id in task.dependencies)
```

## Derived Runtime State

Each task has a runtime view that downstream services can consume:

```json
{
  "task_id": "dp_002",
  "prerequisites_met": false,
  "blocked_by": ["dp_001"],
  "eligible_for_scheduling": false
}
```

## Recalculation Triggers

Prerequisite state must be recalculated whenever:

- A task is completed.
- A task is skipped.
- A task is deleted.
- A task is rescheduled.
- A plan is edited.
- A new plan version is activated.
- A dependency repair occurs.

## Scheduling Implication

Prerequisite enforcement is **two-tier**, and both tiers are deterministic:

- **Deterministic auto-placement (the greedy Scheduler) is hard.** A task with
  unmet prerequisites must not be auto-scheduled before its blockers unless the
  task is explicitly marked as a preview-only future placeholder. For the MVP,
  blocked tasks are not scheduled at all and the Scheduler emits
  `DEPENDENCY_BLOCKED` if asked.
- **A manual placement override is advisory and completion-relative.** When the
  user directly repositions a block (drag-to-adjust, or an adopted external
  calendar move), prerequisite ordering does not refuse the move. A prerequisite
  in the user's completed/dropped set never warns; an *unfinished* prerequisite
  the move now precedes produces a non-blocking `DEPENDENCY_ADVISORY` heads-up,
  and the move is applied. This is still pure code over (dependencies,
  completion/drop state, placement times) — the LLM never marks prerequisites
  met. See `05-scheduler-policy.md` and
  `../decisions/ADR-0008-advisory-manual-ordering.md`.

## Why This Matters

Letting the LLM mark prerequisites met would erase the dependency contract that makes plans safe to schedule. Determinism here is what allows topological scheduling, replanning, and drift detection to remain auditable.

## Related Docs

- `04-validation-layer.md`
- `05-scheduler-policy.md`
- `15-plan-versioning-and-diffs.md`
- `../specs/task-plan.schema.md`
