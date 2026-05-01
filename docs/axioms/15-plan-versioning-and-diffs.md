# 15: Plan Versioning and Deterministic Diffs

## Principle

The active plan must never be mutated directly. New work creates a new plan version. Approvals promote a draft version to active.

```text
plan_001  active
plan_002  draft
plan_003  draft
```

Only after approval:

```text
plan_003 → active
```

## Why

In-place mutation makes drift detection ambiguous, breaks rollback, and prevents the user from comparing drafts. Versioning gives the system clean diffs, audit history, and safe rollback.

## Deterministic Diff: Three-Level Schema

A diff that says "17 tasks rescheduled" gives the user no actionable information. A diff that lists every field change for every task overwhelms. The diff must be hierarchical: summary at the top, drill-down on demand.

The full schema lives in `../specs/plan-diff.schema.md`. The three levels are summarized here.

### Level 1: Headline Summary (always shown)

```json
{
  "summary": {
    "tasks_added": 3,
    "tasks_removed": 1,
    "tasks_rescheduled": 7,
    "tasks_with_duration_changes": 4,
    "modules_affected": ["dynamic_programming", "system_design"],
    "net_weekly_load_change_min": 45,
    "timeline_change_days": 0
  }
}
```

### Level 2: Per-Task Summaries (shown on expand)

```json
{
  "task_changes": [
    {
      "task_id": "dp_003",
      "change_type": "rescheduled",
      "user_facing_summary": "Moved from Tuesday 7pm to Thursday 8pm"
    },
    {
      "task_id": "dp_005",
      "change_type": "duration_changed",
      "user_facing_summary": "Extended from 60 to 90 minutes based on your recent pace"
    }
  ]
}
```

### Level 3: Field-Level Diff (shown on individual task expand or in debug view)

```json
{
  "task_id": "dp_003",
  "field_changes": [
    {
      "field": "scheduled_start",
      "old_value": "2026-05-05T19:00:00-07:00",
      "new_value": "2026-05-07T20:00:00-07:00",
      "delta_minutes": 2820,
      "reason_code": "DEEP_WORK_WINDOW_CONFLICT"
    },
    {
      "field": "estimated_duration_min",
      "old_value": 60,
      "new_value": 90,
      "delta": 30,
      "reason_code": "USER_DURATION_CALIBRATION"
    }
  ]
}
```

### Allowed `change_type` Values

- `added` — task did not exist in the prior plan.
- `removed` — task existed in the prior plan but not in the new one.
- `rescheduled` — same `task_id`, different start/end time.
- `duration_changed` — same `task_id`, different duration.
- `dependency_changed` — same `task_id`, different dependencies.
- `module_reassigned` — same `task_id`, different module.
- `priority_changed` — same `task_id`, different priority.
- `unchanged` — included for completeness, never surfaced to the user.

A single task may carry multiple change types (for example, both `rescheduled` and `duration_changed`); the diff records all of them.

### Reason Codes per Field Change

Every field change must include a typed `reason_code`. Reason codes map to deterministic user-facing strings (the LLM may compose surrounding prose but must not invent reasons):

| Reason Code | User-Facing String |
| --- | --- |
| `DEEP_WORK_WINDOW_CONFLICT` | "to fit your deep work windows" |
| `USER_DURATION_CALIBRATION` | "based on your recent pace" |
| `DEPENDENCY_RESCHEDULED` | "because a prerequisite moved" |
| `WEEKLY_CAPACITY_REBALANCE` | "to balance your weekly load" |
| `EXTERNAL_CALENDAR_CONFLICT` | "because of an event on your calendar" |
| `USER_PROFILE_CHANGE` | "based on your profile update" |
| `DRIFT_REMEDIATION` | "to adapt to your recent completion pattern" |

### Diff Storage and Stability

- Diffs are computed deterministically by code. The LLM is forbidden from generating diffs.
- Every diff is stored in `plan_diff_log` with full Level 3 detail. The UI surfaces Level 1 by default and lazy-loads Levels 2 and 3 on user interaction.
- Diffs are computed between two specific plan versions and are immutable once computed. If the user revisits a diff weeks later, it must be identical to what it was at generation time. This requires storing both the old and new plan snapshots, not recomputing diffs from current state.

The LLM may summarize the diff in user-facing prose, but the diff itself must be computed by code.

## Promotion Rules

A draft can become active only when:

- The draft has a valid `task_plan`.
- The Scheduler succeeded for this draft.
- An `approval_event` exists with `approved: true` and a matching `approved_payload_hash`.
- No active `calendar_write_lock` blocks promotion (see `13-concurrency-model.md`).

## Replan Behavior

When drift triggers replanning:

1. Generate a new draft `plan_version` instead of editing the active plan.
2. Compute the deterministic diff against the active plan.
3. Show the diff in the approval UI.
4. Require approval before any calendar mutation.
5. On approval, promote the new draft to active and run the calendar write flow.

## Rollback Implication

Because the prior plan is preserved, rollback can restore the prior `active_plan_id` even after a failed write. See `06-calendar-safety.md` and `16-reliability-patterns.md`.

## Related Docs

- `02-state-machine.md`
- `06-calendar-safety.md`
- `11-prerequisite-logic.md`
- `13-concurrency-model.md`
- `14-checkpointing-recovery.md`
- `16-reliability-patterns.md`
- `../specs/plan-diff.schema.md`
