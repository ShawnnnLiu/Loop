# 05: Scheduler Policy

## Purpose

The Scheduler is pure deterministic code. It consumes validated tasks and calendar free/busy data and produces a draft schedule only. It must not write to the calendar, request approval, or change plan state by itself.

## Scheduler Inputs

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
  }
}
```

The Scheduler also receives `run_id`, `plan_version`, and current completion state.

## Scheduling Constraints

The Scheduler must respect:

- User availability and timezone.
- Existing calendar free/busy blocks.
- Task dependencies and deterministic prerequisite status.
- Max session length.
- Max daily study time.
- Break requirements between deep blocks.
- Deep work windows.
- Cognitive load distribution.
- No events before or after user-defined bounds.

## Task Ordering Logic

1. Topological sort by dependency graph.
2. Higher-priority modules earlier.
3. Higher cognitive-load tasks placed in deep work windows.
4. Splittable tasks split only by policy.
5. Review tasks may be placed in shorter gaps.
6. Mock interviews require contiguous blocks.
7. Filter tasks whose dependencies are not yet complete.

## Scheduler Output

The Scheduler returns either a draft schedule with task placements or a typed failure with `reason_code`, debug payload, and repair options. See `../specs/scheduler-output.schema.md`.

```json
{
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

## Scheduler Failure Reason Codes

| Reason Code | Meaning | Repair Option |
| --- | --- | --- |
| `NO_VALID_CONTIGUOUS_BLOCK` | No block large enough | Split task or ask user for larger window |
| `INSUFFICIENT_WEEKLY_CAPACITY` | Not enough total time | Extend timeline or reduce scope |
| `DEPENDENCY_BLOCKED` | Required dependency incomplete | Schedule prerequisite first |
| `OUTSIDE_ALLOWED_HOURS` | Candidate window violates user bounds | Find another slot |
| `DAILY_LOAD_EXCEEDED` | Max daily study minutes exceeded | Move task to another day |
| `DEEP_WORK_REQUIRED_UNAVAILABLE` | Deep work task has no deep work window | Ask user or schedule as exception |
| `TASK_TOO_LONG_UNSPLITTABLE` | Task exceeds max block and cannot split | Ask user |

## Repair Options

Scheduler failures may suggest deterministic repair options such as splitting a task, reducing scope, extending the timeline, increasing weekly hours, or relaxing allowed hours. The Scheduler must not mutate the plan directly. The repair flow loops back through Planner and Validator with a hard cap of **2 Scheduler-Planner iterations**.

## Hard Rules

- The Scheduler creates draft schedules only.
- The Scheduler does not call calendar APIs.
- The Scheduler does not bypass validation.
- A task with unmet prerequisites must not be scheduled before its blockers in the MVP.

## Manual Adjustment Re-validation (drag-to-adjust)

Before approval the user may reposition proposed blocks directly (the
schedule-review UI). The Scheduler does not re-run; instead the moved placement
is **re-validated server-side** — the client's own conflict checking is never
trusted — and refused with a typed `reason_code` if it breaks a hard rule. A
manual move must still satisfy:

| Broken on a manual move | `reason_code` |
| --- | --- |
| Overlaps a fixed external event, or another proposed block | `NO_VALID_CONTIGUOUS_BLOCK` |
| Runs outside `[no_events_before, no_events_after]`, or lands on a disabled weekend | `OUTSIDE_ALLOWED_HOURS` |
| Pushes a calendar day over `max_daily_study_min` | `DAILY_LOAD_EXCEEDED` |
| Starts before a prerequisite ends | `DEPENDENCY_BLOCKED` |

A move also never changes a block's **duration** (the new end is derived from the
original length, so a drag cannot resize). What is deliberately **relaxed** for a
manual move is the *soft placement the greedy scheduler optimizes for* but which
is not a hard safety rule: **deep-work-window adherence** and
**`min_break_between_deep_blocks_min`**. The user is explicitly overriding where a
block sits, and the review grid spans a wider day than the deep-work windows;
re-imposing those soft preferences would reject legitimate moves. The hard
day/time/load bounds, no-overlap, and prerequisite order above are not relaxed.
Re-validation lives in `backend/src/agentic_calendar/scheduler/adjustment.py`; the
revised draft is a new immutable `DraftSchedule` whose approval hash is recomputed
from it, so axiom 06's write-time recheck still validates exactly what was
approved.

## Implementation Honesty: Greedy MVP, Solver Later

### MVP Approach: Deterministic Greedy Heuristic

The MVP Scheduler is a deterministic greedy algorithm: topological sort by dependency, ordered by module priority, with cognitive-load-aware placement into available calendar windows. This is a heuristic, not an optimal solver. It will produce visibly suboptimal schedules in adversarial cases, and that tradeoff is accepted for MVP simplicity.

### Acknowledged Limitations

The greedy approach can fail when:

- High-load tasks outnumber available deep-work windows.
- Long task chains with strict dependencies must fit narrow windows.
- Multiple modules compete for the same constrained time slots.
- Task durations cluster awkwardly relative to available block sizes.

In these cases, the Scheduler must fail visibly with typed `reason_code` values and structured repair options rather than silently producing a poor schedule.

### Quality Measurement (Phase 2)

Before upgrading the Scheduler, instrument it to measure:

- Approval rate of first-draft schedules (target: **>70%**).
- Manual edit rate per scheduled task (target: **<25%**).
- Unscheduled task rate per planning cycle (target: **<10%**).
- User-reported schedule quality on a 1–5 scale (sampled).

If approval rate falls below **60%** or manual edit rate exceeds **30%** sustained over 4 weeks of usage, the Scheduler is the bottleneck and warrants an upgrade.

### Phase 3 Upgrade Path

When metrics justify it, migrate to a constraint-programming solver. **Google OR-Tools CP-SAT** is the leading candidate. The upgrade enables:

- Globally optimal placement under hard constraints.
- Soft-constraint optimization (preferences) via weighted objectives.
- Multi-objective optimization (minimize fragmentation, maximize deep-work alignment).
- Provable infeasibility detection rather than greedy give-up.

The CP-SAT migration is a backend-only change. The Scheduler interface (validated tasks in, schedule + reason codes out, defined by `../specs/scheduler-output.schema.md`) does not change. The upgrade can ship without frontend or LLM changes.

### Disclosure

Internal documentation must mark the Scheduler as a "deterministic greedy heuristic — pending Phase 3 solver upgrade." No external claim of "optimal scheduling" should be made until the CP-SAT upgrade is shipped and validated.

## Related Docs

- `04-validation-layer.md`
- `06-calendar-safety.md`
- `11-prerequisite-logic.md`
- `12-edge-case-policy-engine.md`
- `../specs/scheduler-output.schema.md`
