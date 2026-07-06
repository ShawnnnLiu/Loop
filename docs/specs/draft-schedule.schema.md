# Draft Schedule Schema

## Owner

Scheduler post-processing / draft assembly (deterministic; never an LLM).

## Consumers

Approval UI, Calendar Write Manager, approval-payload hasher, audit log.

## Purpose

A draft schedule is the minimal, hashable artifact derived from a `SchedulerOutput`
that represents exactly what the user is asked to approve. It carries only the
fields whose values must be locked at approval time so that a recomputed hash at
write time can prove the payload has not drifted (axiom 06 lines 149–166).

A draft is distinct from a `SchedulerOutput`. `SchedulerOutput` carries
diagnostic and capacity fields (`repair_options`, `available_capacity_min`,
`largest_available_block_min`, `unscheduled_tasks`, etc.) that are useful to
the UI but must not be part of the approval hash; otherwise unrelated
diagnostic changes would invalidate prior approvals.

## JSON Example

```json
{
  "draft_schedule_id": "draft_002",
  "plan_version": "plan_004",
  "entries": [
    {
      "task_id": "dp_002",
      "start": "2026-05-06T19:00:00-07:00",
      "end": "2026-05-06T20:30:00-07:00",
      "calendar_event_status": "draft_only"
    },
    {
      "task_id": "graphs_004",
      "start": "2026-05-07T20:00:00-07:00",
      "end": "2026-05-07T21:00:00-07:00",
      "calendar_event_status": "draft_only"
    }
  ],
  "created_at": "2026-05-04T17:55:00-07:00"
}
```

## Required Fields

- `draft_schedule_id`
- `plan_version`
- `entries` (non-empty, ordered tuple)
- `created_at`

### `entries[*]` Required Fields

- `task_id`
- `start`
- `end`
- `calendar_event_status`

## Field Semantics

| Field | Purpose |
| --- | --- |
| `draft_schedule_id` | Stable identifier; appears on the matching `approval_event` |
| `plan_version` | The immutable plan version this draft was derived from |
| `entries` | Ordered tuple of scheduled placements; order is "scheduled order" per axiom 06 line 153 |
| `entries[*].task_id` | The task being placed |
| `entries[*].start` / `entries[*].end` | Timezone-aware datetimes; `start < end` |
| `entries[*].calendar_event_status` | Always `draft_only` until the Calendar Write Manager creates the external event |
| `created_at` | Timestamp the draft was assembled |

## Invariants

- Drafts are immutable once created (`frozen=True`); revisions produce a new
  `draft_schedule_id`.
- `entries` is non-empty.
- `task_id` values are unique within a single draft.
- Every `start` and `end` is timezone-aware; `end > start`.
- Only drafts derived from `SchedulerOutput` with `schedule_status` in
  `{success, partial_failure}` may be assembled. A `failed` scheduler output
  has no approvable draft.
- Drafts MUST NOT carry any field outside the schema above. UI metadata,
  capacity stats, repair options, and diagnostic payloads belong on the
  `SchedulerOutput`, not the draft.

## Hash Coverage

The `approved_payload_hash` (see `approval-event.schema.md`) is computed over a
canonical serialization of this draft. The hash covers exactly the fields above
in their natural order. The canonical-serialization protocol lives in
`backend/src/agentic_calendar/contracts/hashing.py`; the current version is
registered as `v1`.

`hash_canonicalization_version` on the matching `ApprovalEvent` selects the
canonicalizer used to recompute the hash at write time, so future
canonicalization changes do not invalidate prior approvals.

## Derivation

A draft is assembled by `DraftSchedule.from_scheduler_output(output, *, draft_schedule_id, created_at)`.
The classmethod copies `plan_version` from the scheduler output, copies each
`ScheduledTask` into a `DraftScheduleEntry` preserving scheduled order, and
attaches the supplied `draft_schedule_id` and `created_at`.

## Adjustment (drag-to-adjust)

Before approval, the user may reposition proposed blocks in the schedule-review
UI (`docs/design-reference/design-loop/schedule.jsx`). The backend persists
these moves as a **new draft** — drafts are immutable, so a revision always
gets a fresh `draft_schedule_id` for the same `plan_version`.

A single move is expressed by an **adjustment request item**:

```json
{ "task_id": "graphs_004", "start": "2026-05-08T20:00:00-07:00" }
```

| Field | Purpose |
| --- | --- |
| `task_id` | The proposed entry being moved (must already exist in the draft) |
| `start` | The new timezone-aware start instant; the new day is just a different date here, so a **cross-day move** needs no special field |

`DraftSchedule.with_adjustments(new_starts, *, draft_schedule_id, created_at)`
applies a `{task_id: new_start}` mapping and returns the revised draft:

- **Duration is preserved.** The new `end` is `new_start + (old_end - old_start)`;
  a move can change *when* a block runs but never its length. The request carries
  no `end`, so a client cannot resize a block.
- **Entry order is preserved.** Unmoved entries keep their placement and position;
  only the named tasks change `start`/`end`.
- **Unknown `task_id`s are rejected** (`ValueError`) — a caller cannot introduce a
  task that is not already in the draft, or drop one.
- Structural invariants above (tz-aware, `end > start`, unique ids, non-empty)
  are re-checked by the constructor.

### Server-side re-validation (never trust the client)

The UI's own conflict checking is advisory. Before a revised draft is stored, the
service re-validates the **entire** resulting placement against the user's
scheduling policy and a freshly-fetched free/busy snapshot (see
`backend/src/agentic_calendar/scheduler/adjustment.py`). The validator returns
both **hard conflicts** (which refuse the move) and **advisory warnings** (which
are surfaced but do not block).

A move is **refused** with a typed `reason_code` if any hard rule is broken:

| Hard condition (refuses the move) | `reason_code` |
| --- | --- |
| Overlaps a fixed external event, or another proposed block | `NO_VALID_CONTIGUOUS_BLOCK` |
| Runs outside `[no_events_before, no_events_after]`, or lands on a disabled weekend | `OUTSIDE_ALLOWED_HOURS` |
| Pushes a calendar day over `max_daily_study_min` | `DAILY_LOAD_EXCEEDED` |

A move is **applied with a non-blocking warning** when it breaks only the advisory
ordering rule:

| Advisory condition (warns, move still applied) | `reason_code` |
| --- | --- |
| Starts before an **unfinished** prerequisite ends (one not in the user's completed/dropped set) | `DEPENDENCY_ADVISORY` |

Prerequisite ordering is **completion-relative and advisory** for manual moves
(`../decisions/ADR-0008-advisory-manual-ordering.md`): a prerequisite the user has
already completed or dropped produces no warning, and an unfinished one produces
`DEPENDENCY_ADVISORY` rather than a refusal. The hard `DEPENDENCY_BLOCKED` rule is
kept only by the deterministic auto-placement scheduler, never by a manual
override. The check stays deterministic — pure code over (dependencies,
completion/drop state, placement times).

The overlap and daily-load rules above are hard **for the in-app drag path
only**. Inbound calendar reconciliation reuses this validator in
`overlap_advisory` mode
(`../decisions/ADR-0009-authoritative-external-overlap.md`) and
`daily_load_advisory` mode
(`../decisions/ADR-0010-external-daily-load-advisory.md`): a move the user made
on their own external calendar that overlaps another proposed block or a fixed
busy interval is applied with a non-blocking `OVERLAP_ADVISORY` warning instead
of the `NO_VALID_CONTIGUOUS_BLOCK` refusal, and one that pushes a day over
`max_daily_study_min` is applied with a non-blocking `DAILY_LOAD_ADVISORY`
warning instead of the `DAILY_LOAD_EXCEEDED` refusal — the edit already exists
on the calendar, so refusing it would only leave the plan out of sync. Allowed
hours/weekend stays hard on both paths.

Soft placement that the scheduler *optimizes for* but that is not a hard safety
rule — deep-work-window adherence and `min_break_between_deep_blocks_min` — is
**relaxed for manual moves**: the user is explicitly overriding placement, and
the review grid spans a wider day than the deep-work windows. Adjustment is
allowed **only while the run awaits approval**; the state guard refuses a move
once the draft has been approved (re-approval, not silent mutation, is the
contract). On success the revised draft replaces the pending one and the
approval hash is recomputed from it, so axiom 06's write-time recheck still
validates against exactly what the user approved.

## Invalid Examples

```json
{
  "draft_schedule_id": "draft_002",
  "plan_version": "plan_004",
  "entries": [],
  "created_at": "2026-05-04T17:55:00-07:00"
}
```

Reason: drafts must have at least one entry.

```json
{
  "draft_schedule_id": "draft_002",
  "plan_version": "plan_004",
  "entries": [
    {
      "task_id": "dp_002",
      "start": "2026-05-06T19:00:00-07:00",
      "end": "2026-05-06T19:00:00-07:00",
      "calendar_event_status": "draft_only"
    }
  ],
  "created_at": "2026-05-04T17:55:00-07:00"
}
```

Reason: entry end must be strictly after entry start.

```json
{
  "draft_schedule_id": "draft_002",
  "plan_version": "plan_004",
  "entries": [
    {"task_id": "dp_002", "start": "...", "end": "...", "calendar_event_status": "draft_only"},
    {"task_id": "dp_002", "start": "...", "end": "...", "calendar_event_status": "draft_only"}
  ],
  "created_at": "2026-05-04T17:55:00-07:00"
}
```

Reason: duplicate `task_id` within a draft.

```json
{
  "draft_schedule_id": "draft_002",
  "plan_version": "plan_004",
  "entries": [{"task_id": "dp_002", "start": "2026-05-06T19:00:00", "end": "2026-05-06T20:30:00", "calendar_event_status": "draft_only"}],
  "created_at": "2026-05-04T17:55:00-07:00"
}
```

Reason: naive datetime (no timezone).

## Related Docs

- `../axioms/06-calendar-safety.md` (hash protocol, lines 139–198)
- `approval-event.schema.md`
- `scheduler-output.schema.md`
