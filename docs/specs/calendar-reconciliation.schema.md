# Calendar Reconciliation Schema

## Owner

Calendar Reconciliation Service (deterministic; never an LLM). It reads through
the Calendar Write Manager's adapter seam but is **not** a writer — the Calendar
Write Manager remains the only code that mutates an external calendar
(axiom 06 line 18).

## Consumers

Active-plan lifecycle / Supervisor, deterministic drift classifier (rejected and
deleted deltas), draft-schedule store (adopted moves), `CalendarEventMappingStore`
(sets `user_modified_bool`), telemetry, audit log, and
`UserFacingExplanationNode` (explanation only — it never decides a disposition).

## Purpose

Define the contract for **inbound** calendar reconciliation: detecting that the
user directly edited the app's own events on their dedicated external calendar —
**moved**, **resized**, or **deleted** them — and then deterministically
**adopting valid edits** into the app's internal schedule while **surfacing
invalid edits and deletions as drift**.

Three framing rules govern every clause below:

1. **Read-only against the calendar.** Reconciliation NEVER writes to a calendar.
   It pulls the live state of the app's own events, compares, and updates
   *internal* records. Any calendar change that a user later chooses goes through
   the normal approval + write gate, unchanged.
2. **Opt-in, off by default.** The app's internal schedule is the system of
   record; the external calendar is a sync target, not the source of truth
   (axiom 06 lines 249–253). Treating an external edit as authoritative is
   explicitly opt-in. With the opt-in off, every entry point below is a no-op and
   behavior is identical to today (one-way sync target).
3. **The only writer of `user_modified_bool`.** This service is the sole producer
   of `user_modified_bool: true` on a `calendar_event_mapping`
   (`calendar-event-mapping.schema.md`). That flag means "the external event has
   diverged from our record because the user touched it; never overwrite it
   silently."

## Opt-In Gate (axiom 06 lines 249–253)

- Reconciliation runs only when the acting user has enabled inbound calendar sync
  (`inbound_calendar_sync_enabled`, default `false`).
- When disabled, every trigger is a no-op and the result is `outcome:
  "sync_disabled"` with an empty `deltas` list.
- Rationale: "a move on the external calendar changes the plan" and "a delete on
  the external calendar means the task is cancelled" are exactly the
  external-authoritative behaviors axiom 06 line 253 requires be **explicitly
  opt-in, never default behavior**.
- Storage of the flag is settled in the implementation plan (candidate:
  `OnboardingRecord` / `UserProfile.preferences`); this spec only requires that
  the flag exist, default to `false`, and be user-controllable.

## Trigger (on-demand pull)

The MVP uses on-demand pulls only — **no** webhooks, **no** polling daemon, **no**
`events.watch`.

- A pull is performed for the active run at deterministic entry points: opening
  Today / Week, before `POST /propose` (a replan must see reality), and before
  `POST /checkin` (completion is judged against the real time).
- Each pull is a single metadata-scoped `query_events_by_metadata(run_id)` against
  the dedicated calendar (one round trip per active run).
- Incremental sync (`events.list` + `syncToken`) and push notifications
  (`events.watch` + webhook) are explicit non-goals for the MVP and are recorded
  as the natural follow-ons in the implementation plan.

## The Reconciliation Algorithm (deterministic)

1. **Gate.** If `inbound_calendar_sync_enabled` is false → return
   `outcome: "sync_disabled"`.
2. **Defer to writes.** If a calendar write for this user is in progress
   (`CALENDAR_WRITE_IN_PROGRESS`) or the `calendar_write_lock` is held, return
   `outcome: "deferred"` and perform no comparison (axiom 13). Reads must never
   interleave with an in-flight write.
3. **Pull.** Call `query_events_by_metadata(target_calendar_id, run_id)`; obtain
   the live `scheduled_start`/`scheduled_end` for every event tagged with this
   run's private metadata.
4. **Diff & classify** each mapped task into a `CalendarEventDelta` with a
   `change_type` of `unchanged | moved | resized | deleted` by comparing the live
   times against the mapping's recorded `scheduled_start`/`scheduled_end` (a
   mapped task absent from the result, or whose `read_event` returns `None`, is
   `deleted`).
5. **Re-validate the whole placement.** Substitute every adopted candidate time
   into the active draft and re-validate the **entire** resulting placement
   against the user's scheduling policy and a freshly fetched free/busy snapshot,
   using the same hard rules as drag-to-adjust (`draft-schedule.schema.md`,
   "Server-side re-validation").
6. **Adopt-if-valid.** If the placement validates, assemble a new immutable draft
   schedule with the adopted times, update each affected mapping, and record
   telemetry. No write, no re-approval (no write occurs). State stays
   `ACTIVE_PLAN`.
7. **Flag otherwise.** A move/resize that fails validation, or any deletion, is
   not adopted: the prior internal time remains the system of record, the mapping
   is flagged `user_modified_bool: true`, and a `DRIFT_EXTERNAL_CONFLICT` event is
   emitted so the deterministic drift → replan loop (axiom 07) can surface options
   the user approves through the normal gate.

## JSON Example

```json
{
  "run_id": "run_2026_06_22_001",
  "plan_version": "plan_004",
  "reconciled_at": "2026-06-23T09:05:00-07:00",
  "target_calendar_id": "gcal_dedicated_abc",
  "outcome": "mixed",
  "adopted_draft_schedule_id": "draft_017",
  "deltas": [
    {
      "task_id": "dp_002",
      "calendar_event_id": "gcal_evt_abc123",
      "change_type": "moved",
      "recorded_start": "2026-06-23T19:00:00-07:00",
      "recorded_end": "2026-06-23T20:30:00-07:00",
      "observed_start": "2026-06-24T19:00:00-07:00",
      "observed_end": "2026-06-24T20:30:00-07:00",
      "disposition": "adopted",
      "reason_code": null
    },
    {
      "task_id": "graphs_004",
      "calendar_event_id": "gcal_evt_def456",
      "change_type": "moved",
      "recorded_start": "2026-06-25T20:00:00-07:00",
      "recorded_end": "2026-06-25T21:00:00-07:00",
      "observed_start": "2026-06-25T08:00:00-07:00",
      "observed_end": "2026-06-25T09:00:00-07:00",
      "disposition": "rejected",
      "reason_code": "OUTSIDE_ALLOWED_HOURS"
    }
  ]
}
```

## Required Fields

- `run_id`
- `plan_version`
- `reconciled_at` (timezone-aware)
- `target_calendar_id`
- `outcome`
- `adopted_draft_schedule_id` (nullable; the new draft id when any move was
  adopted, else `null`)
- `deltas` (possibly empty)

### `deltas[*]` Required Fields

- `task_id`
- `calendar_event_id` (nullable only when `change_type` is `deleted`)
- `change_type`
- `recorded_start`, `recorded_end` (the prior internal record; timezone-aware)
- `observed_start`, `observed_end` (the live calendar; both `null` when `deleted`)
- `disposition`
- `reason_code` (typed `ReasonCode`, or `null` when not rejected/deleted)

## Field Semantics

| Field | Purpose |
| --- | --- |
| `run_id` / `plan_version` | The active run and its immutable plan version reconciled against |
| `reconciled_at` | When the pull ran (tz-aware) |
| `target_calendar_id` | The dedicated calendar that was read (never the user's primary) |
| `outcome` | Roll-up: `sync_disabled`, `deferred`, `no_change`, `adopted`, `flagged`, or `mixed` |
| `adopted_draft_schedule_id` | New immutable draft holding the adopted times, or `null` |
| `deltas[*].change_type` | `unchanged \| moved \| resized \| deleted` |
| `deltas[*].disposition` | `unchanged \| adopted \| rejected \| flagged_deleted` |
| `deltas[*].reason_code` | Why a delta was rejected (a hard-rule code) or deleted (`EXTERNAL_EVENT_DELETED`); `null` for `unchanged`/`adopted` |

## Allowed `change_type` Values

- `unchanged`
- `moved` (start changed, duration preserved)
- `resized` (duration changed — possible via an external drag of the event edge;
  the in-app adjust path forbids resize, an external resize does not)
- `deleted`

## Allowed `disposition` Values

- `unchanged`
- `adopted`
- `rejected`
- `flagged_deleted`

## Allowed `reason_code` Values

A delta's `reason_code` is a member of the system-wide `ReasonCode` enum
(`backend/src/agentic_calendar/contracts/reason_codes.py`).

- Rejected moves/resizes reuse the existing drag-to-adjust hard-rule codes, so a
  rejection means the same thing whether the move came from the UI or the
  calendar:
  - `NO_VALID_CONTIGUOUS_BLOCK` (overlaps a fixed external event or another block)
  - `OUTSIDE_ALLOWED_HOURS`
  - `DAILY_LOAD_EXCEEDED`
  - `DEPENDENCY_BLOCKED`
- Deletions use a new typed code **`EXTERNAL_EVENT_DELETED`** (this spec proposes
  its addition to the closed `ReasonCode` enum).
- Every rejected and deleted delta additionally produces a `DriftEvent` of
  `drift_type: external_conflict` / `DRIFT_EXTERNAL_CONFLICT`
  (`drift-event.schema.md`); adopted moves do **not** (no conflict occurred).

## Adopt-If-Valid Rules

- **Whole-placement validation.** Candidate times are validated as a set against
  policy + a freshly fetched free/busy snapshot — never the single moved block in
  isolation, and never the client's own conflict check.
- **Valid → adopt with no write.** Because the user's edit is already on the
  calendar, adoption is a record update, not a write:
  - Assemble a new **immutable** draft schedule (fresh `draft_schedule_id`, same
    `plan_version`) carrying the adopted `start`/`end`. The active *plan* (tasks,
    dependencies, durations) is unchanged, so no new `plan_version` is minted —
    only the schedule placement is revised, exactly as pre-approval drag-to-adjust
    does (`draft-schedule.schema.md`, "Adjustment").
  - Update each affected `calendar_event_mapping` `scheduled_start`/
    `scheduled_end` and set `user_modified_bool: true`.
  - No `approval_event` is required because **no calendar write occurs**; the
    approval / `approved_payload_hash` gate continues to guard the separate write
    path (axiom 06).
  - State stays `ACTIVE_PLAN`.
- **Invalid → flag, never auto-fix.** Keep the prior internal time as the system
  of record, set `user_modified_bool: true` (divergence marker), emit
  `DRIFT_EXTERNAL_CONFLICT` carrying the hard-rule code as evidence, and surface
  it. The engine never silently rewrites the calendar to "correct" the user
  (that would be both a silent write and an override of the user's own calendar).
- **Deleted → detect and surface only (MVP).** Set `user_modified_bool: true`,
  emit `DRIFT_EXTERNAL_CONFLICT`, and surface. The engine never silently
  re-creates the event (it would fight the user) and never silently cancels the
  task (axiom 06 line 253 — cancellation-on-delete is itself opt-in). Richer
  deletion semantics are deferred.

## Privacy Invariants

- Reconciliation reads **only** events bearing this app's private
  `extendedProperties` (`app`, `run_id`) on the **dedicated** calendar; the
  adapter's `DedicatedCalendarViolationError` bounds it to that calendar. It never
  reads the user's other events or other calendars.
- Primary-calendar awareness remains free/busy **intervals only** (no titles, no
  content), exactly as scheduling and adjust already use.
- A `CalendarEventDelta` carries only times, ids, and the four app metadata keys —
  never raw event titles or descriptions (axiom 06 line 91: do not store raw
  calendar event text).
- Net effect: reconciliation reads strictly less of the user's data than the
  write path already does.

## Safety & Determinism Invariants

- Reconciliation performs **no** external calendar mutation under any disposition.
- `reviewMode`/adoption decisions are deterministic functions of (recorded times,
  observed times, policy, free/busy). No LLM influences a `change_type`,
  `disposition`, or `reason_code`; an LLM may only explain a surfaced result.
- Reconciliation defers (no-op) whenever a write is in progress or the
  `calendar_write_lock` is held for the user (axiom 13); adoption that mutates
  mappings is serialized against the write path.
- Adopted moves are user-initiated and are **not** external conflicts: only
  rejected/deleted deltas feed the drift classifier's `external_conflict_task_ids`
  input. Whether adopted moves also increment a reschedule counter for the
  external-conflict correlation rule is a calibration decision, deferred to
  thresholds tuning.

## State-Machine Interaction

- Reconciliation runs in `ACTIVE_PLAN` (and may be invoked while
  `DRIFT_DETECTED`).
- Adoption causes **no** state transition (`ACTIVE_PLAN → ACTIVE_PLAN`, new draft).
- A rejected or deleted delta emits a `DriftEvent`, driving the existing
  `DRIFT_DETECTED` signal and the established replan loop
  (`planner → validation → scheduler → approval`). No new Supervisor states are
  introduced.

## Invariants

- Off by default; a disabled opt-in makes every entry point a no-op
  (axiom 06 lines 249–253).
- Never writes to an external calendar; never requires or mints an
  `approval_event` (no write occurs).
- The only producer of `user_modified_bool: true`.
- Adopts only when the **entire** resulting placement passes the same hard rules
  as drag-to-adjust; partial/optimistic adoption is forbidden.
- Adoption mints a new immutable `draft_schedule_id` under the unchanged
  `plan_version`; the active plan is never mutated in place (axiom 15).
- Every rejected/deleted delta carries a typed `reason_code` and produces a
  `DRIFT_EXTERNAL_CONFLICT` event (axiom: every failure is typed).
- Reads are scoped by app metadata to the dedicated calendar; no raw event text is
  read or stored.
- Deterministic end to end; defers to in-flight writes.

## Invalid Examples

```json
{
  "task_id": "dp_002",
  "change_type": "moved",
  "disposition": "adopted",
  "reason_code": "OUTSIDE_ALLOWED_HOURS"
}
```

Reason: an `adopted` delta must have a `null` `reason_code` — adoption means the
placement validated.

```json
{
  "task_id": "dp_002",
  "change_type": "deleted",
  "observed_start": "2026-06-24T19:00:00-07:00",
  "disposition": "flagged_deleted"
}
```

Reason: a `deleted` delta must have `observed_start`/`observed_end` both `null`.

```json
{
  "run_id": "run_2026_06_22_001",
  "outcome": "adopted",
  "adopted_draft_schedule_id": null,
  "deltas": [{ "task_id": "dp_002", "change_type": "moved", "disposition": "adopted" }]
}
```

Reason: `outcome: "adopted"` requires a non-null `adopted_draft_schedule_id`.

```json
{
  "run_id": "run_2026_06_22_001",
  "outcome": "rejected",
  "deltas": [{ "task_id": "dp_002", "change_type": "moved", "disposition": "rejected", "reason_code": "PLANNER_TIMEOUT" }]
}
```

Reason: a rejected reconciliation delta must use a hard-rule placement code
(`NO_VALID_CONTIGUOUS_BLOCK`, `OUTSIDE_ALLOWED_HOURS`, `DAILY_LOAD_EXCEEDED`,
`DEPENDENCY_BLOCKED`), not an unrelated `ReasonCode`.

## Related Docs

- `../axioms/06-calendar-safety.md` (in-app source-of-truth, lines 249–253; opt-in
  rule; metadata; the write/approval gate this service must not touch)
- `../axioms/07-telemetry-and-drift.md` (`external_conflict` drift + replan loop)
- `../axioms/13-concurrency-model.md` (`calendar_write_lock`; defer-to-write)
- `../axioms/15-plan-versioning-and-diffs.md` (new draft, unchanged plan version)
- `../axioms/19-always-online-mvp.md` (on-demand pull, online)
- `calendar-event-mapping.schema.md` (`user_modified_bool`, `scheduled_*`)
- `draft-schedule.schema.md` (adjustment re-validation rules reused here)
- `drift-event.schema.md` (`DRIFT_EXTERNAL_CONFLICT` routing)
- `telemetry.schema.md`
- `validation-result.schema.md`
- `../decisions/ADR-0002-preview-only-calendar-writes.md`
- `../decisions/ADR-0006-llm-never-touches-the-calendar.md`
