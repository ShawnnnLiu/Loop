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
    "allow_weekends": true,
    "min_break_between_deep_blocks_min": 30,
    "max_daily_study_min": 180,
    "respect_deep_work_windows": true,
    "deep_work_windows": [
      { "day": "Mon", "start": "18:00", "end": "21:00" }
    ],
    "max_session_length_min": 120,
    "preferred_session_length_min": 60,
    "prefer_evening_sessions": false,
    "prefer_weekend_long_blocks": false,
    "avoid_back_to_back_deep_work": false
  }
}
```

This block is the spec for the region-local `SchedulingPolicy` model
(`backend/src/agentic_calendar/scheduler/policy.py`). There is no separate
`max_contiguous_study_min`; the scheduler uses `max_session_length_min` as
the per-task cap. The three `prefer_*`/`avoid_*` booleans and
`preferred_session_length_min` mirror the user profile's soft preferences
and preferred session length; they feed the scored-placement terms below
and never tighten a hard constraint.

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

## Scored Placement

Within the ordered task loop, placement is a deterministic argmin over
enumerated feasible candidates — not "first window's start wins."

### Candidate enumeration

- For each free window, candidate starts are the window start plus a fixed
  15-minute intra-window grid: `window.start + k × candidate_grid_min`
  for every integer `k ≥ 0` with `candidate_start + duration ≤ window.end`
  (the `k = 0` element is the window start itself).
- Every candidate must pass all hard checks — window size, deep-window
  requirement, window-end bound, daily study cap, break-between-deep-blocks
  gap. Scoring never relaxes a hard constraint.

### Integer cost function

```
cost(candidate) = Σ w_term × penalty_term − Σ w_term × bonus_term
```

Each `penalty_term` / `bonus_term` is a non-negative minutes-scaled
integer; every weight is an integer. Placement uses integer arithmetic
only. The term list (exact formulas live in
`../implementation-plans/scheduler-placement-quality/01-scored-placement.md`):

| Term | Sign | Intent |
| --- | --- | --- |
| `daily_balance` | penalty | placement pushing a day past its even-spread daily target |
| `back_to_back` | penalty | gap to an adjacent placed study block below the buffer; doubled for a deep block adjacent to another deep block when `avoid_back_to_back_deep_work` |
| `fragmentation` | penalty | leaving an unusable sliver (`0 < leftover < preferred_session_length_min`) in the window |
| `deep_window_conservation` | penalty | a non-deep task consuming scarce deep-window capacity |
| `evening_preference` | bonus | evening-band start when `prefer_evening_sessions` |
| `weekend_long_block` | bonus | weekend placement of a task longer than `preferred_session_length_min` when `prefer_weekend_long_blocks` and weekends are allowed |

### Selection and tie-break

The chosen candidate is the argmin under the total-order key
`(cost, candidate_start)`. Free windows are disjoint and grid starts within
a window are distinct, so no two candidates share a start — the order is
total and placement is fully deterministic.

### Weights are heuristic priors

Term weights and placement knobs (`buffer_min`, `candidate_grid_min`) are
tunable only via `backend/tuning.toml` (`[scheduler_placement]`); overrides
are journaled through the threshold change log, following axiom 07's
pattern. Until calibrated against real usage they are heuristic priors and
must be described as such.

### Soft terms never eliminate feasibility

Scoring reorders feasible candidates; it never rejects one. Any task that
first-fit placement would have scheduled remains schedulable under scored
placement (the grid strictly adds candidates), and every failure keeps the
typed `reason_code` produced by the hard checks.

### Rollout status

Live. The candidate machinery shipped behavior-identical to first fit
first (window-start candidates only, cost ≡ 0) with an output-equivalence
proof; the scoring-terms increment then activated the intra-window grid
and the six cost terms above, deliberately re-pinning placement-instant
test expectations while leaving every reason_code, debug payload, and
Supervisor routing assertion unchanged. Weights and knobs serve from
`PlacementScoringConfig` defaults unless overridden via
`backend/tuning.toml` `[scheduler_placement]`.

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
- The Scheduler's deterministic auto-placement must not schedule a task with unmet
  prerequisites before its blockers in the MVP (`DEPENDENCY_BLOCKED`). A **manual**
  placement override is governed by the advisory rule under "Manual Adjustment
  Re-validation" (`DEPENDENCY_ADVISORY`), not this hard rule. See
  `../decisions/ADR-0008-advisory-manual-ordering.md`.

## Manual Adjustment Re-validation (drag-to-adjust)

Before approval the user may reposition proposed blocks directly (the
schedule-review UI). The Scheduler does not re-run; instead the moved placement
is **re-validated server-side** — the client's own conflict checking is never
trusted — and refused with a typed `reason_code` if it breaks a hard rule. A
manual move must still satisfy:

| Broken on a manual move (hard — refused) | `reason_code` |
| --- | --- |
| Overlaps a fixed external event, or another proposed block | `NO_VALID_CONTIGUOUS_BLOCK` |
| Runs outside `[no_events_before, no_events_after]`, or lands on a disabled weekend | `OUTSIDE_ALLOWED_HOURS` |
| Pushes a calendar day over `max_daily_study_min` | `DAILY_LOAD_EXCEEDED` |

**Prerequisite ordering on a manual move is advisory, not a refusal**
(`../decisions/ADR-0008-advisory-manual-ordering.md`). Dragging a block before a
prerequisite that is *unfinished* — not in the user's completed/dropped set —
yields a non-blocking `DEPENDENCY_ADVISORY` warning and the move is still applied;
a prerequisite the user has already completed or dropped yields no warning at all.
The check stays deterministic and completion-relative. Only the deterministic
auto-placement keeps the hard `DEPENDENCY_BLOCKED` rule. This narrows — it does
not remove — the prerequisite guarantee: auto-placement is still topologically
ordered, and the user's own override is surfaced rather than walled.

A move also never changes a block's **duration** (the new end is derived from the
original length, so a drag cannot resize). What is deliberately **relaxed** for a
manual move is the *soft placement the greedy scheduler optimizes for* but which
is not a hard safety rule: **deep-work-window adherence** and
**`min_break_between_deep_blocks_min`**. The user is explicitly overriding where a
block sits, and the review grid spans a wider day than the deep-work windows;
re-imposing those soft preferences would reject legitimate moves. The hard
day/time/load bounds and no-overlap rule above are not relaxed. Prerequisite
ordering, by contrast, is relaxed for a manual move to the advisory
`DEPENDENCY_ADVISORY` heads-up described above (it remains hard only for
deterministic auto-placement).

The no-overlap and daily-load rules are hard **for the in-app drag only**. An
**external** move — the user repositioning an already-written event on their
own Google Calendar, picked up by inbound reconciliation — treats overlap as
advisory (`OVERLAP_ADVISORY`,
`../decisions/ADR-0009-authoritative-external-overlap.md`) and daily load as
advisory (`DAILY_LOAD_ADVISORY`,
`../decisions/ADR-0010-external-daily-load-advisory.md`): the edit already
exists on the user's calendar, so the reconciliation service adopts it and
surfaces the overlap or over-cap day rather than refusing an accomplished fact.
The daily cap stays hard everywhere the *system* chooses placements —
auto-placement and the in-app drag. Allowed hours/weekend remains hard on both
paths.
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
