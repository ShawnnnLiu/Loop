# Scheduler Output Schema

## Owner

Deterministic Scheduler.

## Consumers

Supervisor, approval UI, Calendar Write Manager, user-facing explanations.

## Purpose

The Scheduler always returns a draft. It never writes to the calendar. The output captures scheduled tasks, unscheduled tasks with typed failure reasons, capacity diagnostics, and deterministic repair options.

## Inputs

```json
{
  "validated_tasks": [],
  "user_profile": {},
  "calendar_free_busy": [
    {
      "start": "2026-05-04T09:00:00-07:00",
      "end": "2026-05-04T10:00:00-07:00"
    }
  ],
  "scheduling_policy": {
    "no_events_before": "08:00",
    "no_events_after": "22:30",
    "max_contiguous_study_min": 120,
    "min_break_between_deep_blocks_min": 30,
    "max_daily_study_min": 180,
    "respect_deep_work_windows": true
  },
  "run_id": "run_2026_05_04_001",
  "plan_version": "plan_004"
}
```

## JSON Example

```json
{
  "run_id": "run_2026_05_04_001",
  "plan_version": "plan_004",
  "schedule_status": "partial_failure",
  "scheduled_tasks": [
    {
      "task_id": "dp_001",
      "start": "2026-05-04T18:00:00-07:00",
      "end": "2026-05-04T19:00:00-07:00",
      "calendar_event_status": "draft_only"
    }
  ],
  "unscheduled_tasks": [
    {
      "task_id": "dp_002",
      "reason_code": "NO_VALID_CONTIGUOUS_BLOCK",
      "debug": {
        "required_duration_min": 90,
        "largest_available_block_min": 60,
        "required_focus_level": "deep",
        "candidate_windows_checked": 8,
        "rejected_windows": [
          {
            "start": "2026-05-05T20:00:00-07:00",
            "duration_min": 60,
            "rejection_reason": "too_short"
          },
          {
            "start": "2026-05-06T21:30:00-07:00",
            "duration_min": 90,
            "rejection_reason": "ends_after_user_limit"
          }
        ],
        "suggested_repair": "split_task"
      }
    }
  ],
  "available_capacity_min": 240,
  "largest_available_block_min": 60,
  "repair_options": [
    "split_large_tasks",
    "extend_timeline",
    "reduce_scope",
    "increase_weekly_hours"
  ]
}
```

## Allowed `schedule_status` Values

- `success` — every validated task is scheduled.
- `partial_failure` — at least one task could not be scheduled.
- `failed` — no tasks could be scheduled.

## Reason Codes

| Reason Code | Meaning | Repair Option |
| --- | --- | --- |
| `NO_VALID_CONTIGUOUS_BLOCK` | No block large enough | Split task or ask user for larger window |
| `INSUFFICIENT_WEEKLY_CAPACITY` | Not enough total time | Extend timeline or reduce scope |
| `DEPENDENCY_BLOCKED` | Required dependency incomplete | Schedule prerequisite first |
| `OUTSIDE_ALLOWED_HOURS` | Candidate window violates user bounds | Find another slot |
| `DAILY_LOAD_EXCEEDED` | Max daily study minutes exceeded | Move task to another day |
| `DEEP_WORK_REQUIRED_UNAVAILABLE` | Deep work task has no deep work window | Ask user or schedule as exception |
| `TASK_TOO_LONG_UNSPLITTABLE` | Task exceeds max block and cannot split | Ask user |

## Invariants

- Scheduler output is always a draft, never a calendar write.
- `unscheduled_tasks[*]` must include `reason_code` and `debug`.
- Successful scheduled placements must reference `task_id` and timestamps in the user's timezone.
- `available_capacity_min` and `largest_available_block_min` are non-negative integers.
- `repair_options` may be empty only when status is `success`.
- The Scheduler must not include `calendar_event_id` for any task.

## Invalid Examples

```json
{
  "schedule_status": "partial_failure",
  "unscheduled_tasks": [{ "task_id": "dp_002" }]
}
```

Reason: missing typed `reason_code` and debug payload.

```json
{
  "schedule_status": "success",
  "scheduled_tasks": [
    { "task_id": "dp_001", "calendar_event_id": "abc123" }
  ]
}
```

Reason: Scheduler cannot create calendar events.

```json
{ "schedule_status": "failed", "reason_code": null, "debug": {} }
```

Reason: failure lacks typed reason.

## Related Docs

- `../axioms/05-scheduler-policy.md`
- `../axioms/12-edge-case-policy-engine.md`
- `approval-event.schema.md`
- `calendar-event-mapping.schema.md`
