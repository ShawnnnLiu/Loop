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
