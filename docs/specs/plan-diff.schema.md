# Plan Diff Schema

## Owner

Deterministic diff service.

## Consumers

Approval UI, replan flow, audit log, `UserFacingExplanationNode`.

## Purpose

Compute the difference between two plan versions deterministically. The LLM may summarize the diff in friendly language, but the diff itself must be computed by code.

The diff is **hierarchical**. It exposes three levels: a headline summary, per-task summaries, and field-level changes. The UI shows Level 1 by default and lazy-loads Levels 2 and 3 on user interaction.

## JSON Example

```json
{
  "diff_id": "diff_2026_05_07_001",
  "from_plan_version": "plan_003",
  "to_plan_version": "plan_004",
  "computed_at": "2026-05-07T18:00:00-07:00",
  "summary": {
    "tasks_added": 3,
    "tasks_removed": 1,
    "tasks_rescheduled": 7,
    "tasks_with_duration_changes": 4,
    "modules_affected": ["dynamic_programming", "system_design"],
    "net_weekly_load_change_min": 45,
    "timeline_change_days": 0
  },
  "task_changes": [
    {
      "task_id": "graphs_004",
      "change_type": "added",
      "user_facing_summary": "Added: Solve weighted graph practice set"
    },
    {
      "task_id": "dp_007",
      "change_type": "removed",
      "user_facing_summary": "Removed: Advanced bitmask DP set"
    },
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
  ],
  "field_changes": [
    {
      "task_id": "dp_003",
      "field": "scheduled_start",
      "old_value": "2026-05-05T19:00:00-07:00",
      "new_value": "2026-05-07T20:00:00-07:00",
      "delta_minutes": 2820,
      "reason_code": "DEEP_WORK_WINDOW_CONFLICT"
    },
    {
      "task_id": "dp_005",
      "field": "estimated_duration_min",
      "old_value": 60,
      "new_value": 90,
      "delta": 30,
      "reason_code": "USER_DURATION_CALIBRATION"
    }
  ]
}
```

## Top-Level Fields

| Field | Purpose |
| --- | --- |
| `diff_id` | Stable identifier for the diff record |
| `from_plan_version` | Older plan version being compared |
| `to_plan_version` | Newer plan version being proposed |
| `computed_at` | Timestamp the diff was computed |
| `summary` | Level 1 headline summary, always shown |
| `task_changes` | Level 2 per-task summaries, shown on expand |
| `field_changes` | Level 3 field-level diffs, shown in detail view |

## Level 1: `summary`

| Field | Purpose |
| --- | --- |
| `tasks_added` | Count of `added` changes |
| `tasks_removed` | Count of `removed` changes |
| `tasks_rescheduled` | Count of `rescheduled` changes |
| `tasks_with_duration_changes` | Count of `duration_changed` changes |
| `modules_affected` | Distinct `module_id` values touched by any change |
| `net_weekly_load_change_min` | Signed integer; positive means more work |
| `timeline_change_days` | Signed integer; positive means timeline extended |

## Level 2: `task_changes[*]`

| Field | Purpose |
| --- | --- |
| `task_id` | Affected task |
| `change_type` | One of the allowed change types below |
| `user_facing_summary` | Deterministic short string for UI display |

A single task may appear multiple times in `task_changes` if it has multiple change types (for example, `rescheduled` and `duration_changed`).

### Allowed `change_type` Values

- `added`
- `removed`
- `rescheduled`
- `duration_changed`
- `dependency_changed`
- `module_reassigned`
- `priority_changed`
- `unchanged` (included only for completeness, never surfaced to users)

## Level 3: `field_changes[*]`

| Field | Purpose |
| --- | --- |
| `task_id` | Affected task |
| `field` | Specific field that changed |
| `old_value` | Prior value |
| `new_value` | New value |
| `delta` / `delta_minutes` | Signed delta when applicable |
| `reason_code` | Typed reason for the change |

### Allowed `reason_code` Values

| Reason Code | User-Facing String |
| --- | --- |
| `DEEP_WORK_WINDOW_CONFLICT` | "to fit your deep work windows" |
| `USER_DURATION_CALIBRATION` | "based on your recent pace" |
| `DEPENDENCY_RESCHEDULED` | "because a prerequisite moved" |
| `WEEKLY_CAPACITY_REBALANCE` | "to balance your weekly load" |
| `EXTERNAL_CALENDAR_CONFLICT` | "because of an event on your calendar" |
| `USER_PROFILE_CHANGE` | "based on your profile update" |
| `DRIFT_REMEDIATION` | "to adapt to your recent completion pattern" |

The LLM may compose surrounding prose, but the source phrases come from this table.

## Invariants

- Diff is computed by deterministic code, not by an LLM.
- `from_plan_version` must reference an existing plan version.
- `to_plan_version` must reference a draft or active plan version.
- `from_plan_version` must differ from `to_plan_version`.
- A `task_id` cannot appear in both `added` and `removed` task changes.
- Every entry in `field_changes` must reference a `task_id` and `change_type` represented in `task_changes`.
- Every `field_changes[*].reason_code` must be in the allowed set above.
- `summary.modules_affected` must be the deduplicated union of modules from `task_changes`.
- Diffs are read-only and immutable once computed; they do not mutate either plan.
- Diffs persist with full Level 3 detail in `plan_diff_log` so historical views remain stable.

## Use in the Approval Flow

When the system replans, it must:

1. Build a new draft plan version.
2. Compute the deterministic diff against the active plan.
3. Show Level 1 in the approval UI, with Levels 2–3 lazy-loaded on expand.
4. Require explicit approval before any calendar mutation.

See `../axioms/15-plan-versioning-and-diffs.md`.

## Invalid Examples

```json
{
  "from_plan_version": "plan_003",
  "to_plan_version": "plan_003"
}
```

Reason: same plan on both sides; nothing to diff.

```json
{
  "task_changes": [
    { "task_id": "dp_001", "change_type": "added" },
    { "task_id": "dp_001", "change_type": "removed" }
  ]
}
```

Reason: a task cannot be both added and removed.

```json
{
  "field_changes": [
    {
      "task_id": "dp_003",
      "field": "estimated_duration_min",
      "old_value": -10,
      "new_value": 60,
      "reason_code": "USER_DURATION_CALIBRATION"
    }
  ]
}
```

Reason: invalid prior duration.

```json
{
  "field_changes": [
    {
      "task_id": "dp_003",
      "field": "scheduled_start",
      "reason_code": "MOVED_BECAUSE_VIBES"
    }
  ]
}
```

Reason: unknown `reason_code`.

## Related Docs

- `../axioms/15-plan-versioning-and-diffs.md`
- `../axioms/16-reliability-patterns.md`
- `task-plan.schema.md`
- `approval-event.schema.md`
