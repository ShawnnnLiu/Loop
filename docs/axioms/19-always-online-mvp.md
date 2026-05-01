# 19: Always-Online MVP and Offline Completion Exception

## Online-First Rule

The MVP is **always-online for plan mutations and calendar writes**.

- No offline plan generation.
- No offline calendar writes.
- No offline schedule edits.

Offline plan mutation requires event sourcing and conflict resolution. Those capabilities must not be introduced before the online system is reliable.

## Offline Client Behavior for Plan Mutations

If the client loses connection, the system must:

- Show a read-only cached view of plan and schedule structure.
- Disable plan editing actions.
- Disable calendar write actions.
- Resume normal mutation when the connection returns.

The client must never queue local plan mutations for later sync.

## Offline Task Completion (Allowed Exception)

### Why an Exception

The MVP is online-first for **plan mutations and calendar writes**, but users will study offline (planes, subways, focus mode, hotel Wi-Fi failures) and need to record completion data when they reconnect. Forcing online connectivity for completion would cause users to silently stop logging tasks, which destroys the telemetry that calibration and drift detection depend on.

This is the **only** allowed offline mutation in the MVP, and it is deliberately scoped to telemetry only.

### Required vs Optional Telemetry Inputs

**Required at completion (online or offline once synced):**

- `completed`
- `task_id`

**Optional but recommended at completion:**

- `actual_duration_min`
- `completion_timestamp`
- `subjective_difficulty` (1–5 self-report)

**Computed if not provided:**

- If `actual_duration_min` is missing, default to `scheduled_duration_min` and flag the event as `data_quality: "partial_estimated"` so the calibration engine can exclude or down-weight it.
- If `completion_timestamp` is missing, default to the scheduled end time and tag with the same flag.

### Productivity vs Data Quality Tradeoff

Required fields must be minimized to maximize completion rate. If marking a task complete requires answering five questions, users will stop marking tasks complete and the system will lose all data. Partial data is better than no data.

### Recommended UX

- Default — one-tap "Done" button records `completed: true` with estimated values.
- Expanded — "Done + log details" captures actual duration and subjective difficulty.
- In-app prompts may encourage detail logging, but completion must never be blocked on it.

### Offline Completion Queue

When offline:

1. Show the cached schedule as read-only with completion buttons enabled.
2. Store completion events in a local queue with provisional timestamps.
3. On reconnect, sync queued events to the telemetry log.
4. If conflicts exist (for example, a task was rescheduled server-side after the user marked it complete on the offline client), surface a reconciliation dialog. Never silently pick a winner.

### Telemetry Quality Tagging

Every telemetry event includes a `data_quality` field with one of:

- `complete` — all fields user-provided.
- `partial_estimated` — duration or timestamp inferred.
- `offline_synced` — captured offline, synced later.
- `manual_backfill` — entered hours or days after the fact.

The calibration engine weights these differently. For example, `complete` events count fully while `manual_backfill` events count at **0.5 weight**. The drift classifier may also exclude `partial_estimated` events from samples below its minimum sample size.

### Reconciliation Rules

On sync, the server is authoritative for plan structure but the client is authoritative for completion intent:

- If a task still exists server-side, accept the offline completion event.
- If a task was deleted server-side before the offline event, store the event with `data_quality: "offline_synced"` and surface it in the reconciliation dialog.
- If a task was rescheduled server-side, accept the completion event and mark the calendar event mapping as `user_modified_bool: true`.

## Why

Online-first behavior gives the system one source of truth for plan and schedule state. Approval, calendar writes, verification, and drift classification all require server-authoritative state. The narrow exception for completion telemetry is the smallest deviation that protects user data quality without compromising plan-mutation invariants.

## Future Considerations

Broader offline mode may be revisited after Phase 5, but only with:

- Event sourcing for plan and telemetry mutations.
- Server-authoritative conflict resolution.
- Explicit user-visible sync states.
- Tests that prove approval and calendar safety invariants survive offline edits.

## Related Docs

- `06-calendar-safety.md`
- `07-telemetry-and-drift.md`
- `10-mvp-roadmap.md`
- `17-duration-estimation.md`
- `21-accountability-layer.md`
- `../specs/telemetry.schema.md`
- `../decisions/ADR-0003-no-offline-mode-in-mvp.md`
