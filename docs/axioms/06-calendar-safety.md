# 06: Calendar Safety

## Non-Negotiable Rule

**No silent calendar writes ever.**

Every calendar mutation must be preceded by:

1. Draft schedule generation.
2. User-visible preview.
3. Explicit user approval.
4. Recorded `approval_event`.
5. Verified write.

## Ownership

- Scheduler cannot write to a calendar.
- Calendar Write Manager is the only writer.
- Calendar Write Manager accepts only approved draft schedules.
- Calendar Write Manager must support dry-run, write, verify, and rollback modes.

## Calendar States

```text
draft_schedule_created
awaiting_user_approval
calendar_write_approved
calendar_write_in_progress
calendar_write_verified
calendar_write_failed
```

## Approval Gate Rules

| Trigger | UI Default | Calendar Write Allowed? |
| --- | --- | --- |
| Initial schedule generated | Preview schedule | No |
| User edits draft schedule | Preview changes | No |
| Replan generated | Show diff | No |
| Drift remedy suggested | Show options | No |
| Calendar conflict detected | Preview reschedule | No |
| Scheduler-Planner loop exhausted | Ask user | No |
| User clicks "Add to Calendar" | Write approved | Yes |

## Required Write Fields

Every calendar write requires:

- `approval_event_id`
- `run_id`
- `plan_version`
- `task_id`
- target calendar identifier
- `approved_payload_hash`

Missing any required field must fail before any external API call.

## Invariant

**No `approval_event_id` → no calendar write.**

This invariant must be checked immediately before any calendar mutation.

## Calendar Event Metadata

Every event created by the app must include identifying metadata:

```json
{
  "extendedProperties": {
    "private": {
      "app": "career_scheduler",
      "run_id": "run_2026_05_04_001",
      "plan_version": "plan_004",
      "task_id": "dp_002"
    }
  }
}
```

## Local Event Mapping

The system stores a local mapping per write:

- `task_id`
- `plan_version`
- `run_id`
- `calendar_event_id`
- `scheduled_start`
- `scheduled_end`
- `calendar_write_status`
- `user_modified_bool`
- `last_verified_at`

See `../specs/calendar-event-mapping.schema.md`.

## Write Flow

1. Confirm `approval_event_id` exists and approval is `true`.
2. Verify `approved_payload_hash` matches the draft payload.
3. Acquire user `calendar_write_lock`.
4. Generate `run_id`.
5. Run dry-run validation.
6. For each scheduled task, create the event with `run_id` and `task_id` metadata.
7. Store the local event mapping.
8. Query the calendar to verify each event exists.
9. Mark `calendar_write_verified`.
10. Release `calendar_write_lock`.

## Partial Failure Recovery

1. Query calendar events by `run_id`.
2. Compare returned `task_id` list against expected list.
3. If extra events exist, mark duplicate risk and escalate.
4. If missing events exist, retry only those `task_id` writes if safe.
5. If rollback policy applies, delete all events with the run's `run_id`.
6. Verify final state.
7. Mark write as verified or failed.

## Duplicate Prevention

The system must never blindly retry a calendar write. It must first query by `run_id` and `task_id` to determine what already succeeded. Duplicate detection uses metadata, not title matching.

## Verification Rules

- Verify external event ID exists.
- Verify `run_id`, `plan_version`, and `task_id` metadata.
- Verify scheduled start and end match the approved payload.
- Detect duplicates by metadata before creating events.
- Mark verification failures with a typed `reason_code`.

## Rollback Rules

- Rollback uses stored `calendar_event_mapping` and metadata, not fuzzy title matching.
- Rollback deletes events by `run_id`.
- If rollback cannot confirm deletion, mark the mapping as `rollback_failed` and escalate to user attention.
- Every automated write must have a corresponding rollback path. If rollback is not defined, the action must not be automated.

## Approval Payload Hashing

### The Stale Approval Problem

Without payload binding, an approval event for plan A could authorize a write of plan B if the system mutates the draft between approval and write. This breaks the "user approved exactly what was written" guarantee.

### Hashing Protocol

#### At Draft Creation

Compute `draft_payload_hash` over the canonical serialization of the draft schedule.

The hash **must cover**:

- All `task_id` values in scheduled order.
- All `start` and `end` timestamps.
- All `calendar_event_status` flags.
- The `plan_version` ID.
- The `draft_schedule_id`.

The hash **must not cover**:

- UI metadata (display labels, color themes).
- Non-scheduling fields (notes, descriptions).
- Server timestamps unrelated to schedule semantics.

Use a canonical serialization (sorted keys, no whitespace) so the hash is stable across serializers. **SHA-256** is the required algorithm for the MVP.

#### At Approval

The approval event records the hash and the canonicalization version it was computed against:

```json
{
  "approval_event_id": "approval_123",
  "draft_schedule_id": "draft_002",
  "approved_payload_hash": "sha256:abc123...",
  "hash_algorithm": "sha256",
  "hash_canonicalization_version": "v1"
}
```

#### At Write Time (Mandatory Check)

The Calendar Write Manager must:

1. Re-fetch the draft schedule.
2. Recompute the payload hash using the same canonicalization version recorded on the approval.
3. Compare to `approval_event.approved_payload_hash`.
4. If mismatch → **abort the write**, log `APPROVAL_HASH_MISMATCH`, and surface the user-facing message: "The plan changed after you approved it. Please review and re-approve."
5. If match → proceed with the write.

### Hash Versioning

The `hash_canonicalization_version` allows the canonicalization algorithm to evolve without invalidating old approvals. If the serialization changes, increment the version. Old approvals are still validated against their original version's algorithm.

### Time-Based Invalidation

Approval events expire after **24 hours**. After expiry, the hash check is skipped because the user must re-approve regardless. This prevents stale approvals from being silently honored if the system is offline for an extended period.

### Audit Logging

Every hash check (pass or fail) is logged with:

- `approval_event_id`
- recomputed hash
- approved hash
- result (`match`, `mismatch`, `expired`)

Hash mismatches are flagged as **P1 incidents** because they indicate either a bug or a security issue.

## Calendar Write UX and Crash Recovery

### The Long-Write Problem

A typical week of scheduled tasks may produce 8–15 calendar events. Google Calendar API writes are sequential and rate-limited; a full write can take 10–30 seconds. Without explicit UX, this looks like the app is frozen or broken.

### Required UX During Calendar Writes

- **Optimistic UI on approval.** The instant the user clicks "Add to Calendar," update the in-app UI to show events as scheduled, not pending. Disable further plan mutations until the write completes.
- **Progress indicator.** Display a non-blocking status banner: "Syncing 12 events to Google Calendar — 4 of 12 done." The banner is dismissible but reappears on the schedule view until sync completes.
- **Event-level state.** Each event in the in-app schedule shows its sync state: `local`, `syncing`, `synced`, or `failed`. Users can see exactly which events made it to Google Calendar.
- **No blocking modal.** Never use a full-screen "Please wait" modal. Users must be able to navigate away, view other plans, or close the app.
- **Background completion.** If the user closes the app mid-write, the write continues server-side. On reopening, the user sees the final state.

### Crash Recovery: Local-First Fallback

If the calendar write process crashes, hangs beyond timeout, or the lock holder dies:

1. **Abandon the external write.** Do not retry the Google Calendar write automatically. Mark the run as `external_sync_failed` with a typed `reason_code`.
2. **Preserve in-app state.** All scheduled tasks remain valid in the app's internal calendar. The user can view them, complete them, and reschedule them within the app.
3. **Surface a sync action.** Show a persistent "Sync to Google Calendar" button on the schedule view with explanatory text: "Some events didn't sync to Google Calendar. Tap to retry."
4. **Manual retry only.** Sync retries are user-triggered, never automatic. This prevents thrashing if the underlying issue (auth expired, API down, quota exceeded) persists.
5. **Reconciliation on retry.** Before retrying, query Google Calendar for events matching `run_id` and `task_id`. Only write events that are confirmed missing. Never duplicate.

### Lock Recovery

The `calendar_write_lock` must support:

- A TTL of **120 seconds** (longer than expected write time, shorter than user patience).
- Heartbeat extension while the write is actively progressing.
- Automatic release on TTL expiry.
- A cleanup job that runs hourly to release zombie locks.

When a lock expires due to crash:

- The associated run is marked `external_sync_failed`.
- The user is shown the manual retry UI.
- No automatic recovery is attempted.

### In-App Calendar as Source of Truth

This is a deliberate product decision: **the app's internal schedule is the authoritative source of what the user is supposed to do**. Google Calendar (or any other external calendar) is a sync target, not the system of record. This decision protects the user from broken external integrations and makes the app usable even without calendar sync configured.

Any feature that depends on the external calendar being authoritative (for example, "delete from Google Calendar means the task is cancelled") must be explicitly opt-in, never default behavior.

## Typed Reason Codes (Phase 2)

Every Phase 2 calendar-safety failure produces one of the typed `ReasonCode`
values below. These codes are exhaustive for the Calendar Write Manager and
the approval flow; consumers (telemetry, audit log, `UserFacingExplanationNode`)
may rely on the enumeration being closed.

| `ReasonCode` | Trigger | Recoverable? |
| --- | --- | --- |
| `APPROVAL_MISSING` | Write attempted with no matching `approval_event_id`. | Yes — user re-approves. |
| `APPROVAL_EXPIRED` | Approval's `expires_at` ≤ `clock.now()` at write time. | Yes — user re-approves. |
| `APPROVAL_HASH_MISMATCH` | Recomputed hash differs from `approved_payload_hash`. **P1 incident.** | Yes — user reviews and re-approves the (changed) draft. |
| `APPROVAL_HASH_ALGORITHM_UNSUPPORTED` | Approval's `hash_algorithm` is not in the allowed set. | No — reject; log. |
| `CALENDAR_WRITE_LOCK_BUSY` | Another write for the same user holds the lock. | Yes — caller retries after backoff. |
| `CALENDAR_WRITE_LOCK_EXPIRED` | Holder's lock token expired mid-write (TTL or cleanup eviction). | Manual retry only (see "Crash Recovery"). |
| `CALENDAR_WRITE_DUPLICATE_DETECTED` | Pre-write metadata query found events already tagged with this `run_id`. | Manual investigation; no auto-retry. |
| `CALENDAR_WRITE_FAILED` | Adapter create-event call raised. | Per axiom 06 lines 110–118; reconcile by `run_id`. |
| `CALENDAR_VERIFICATION_FAILED` | Post-write read-back found mismatched metadata or times. | Mark `verification_failed`; route rollback. |
| `CALENDAR_ROLLBACK_FAILED` | Adapter delete-event call raised during rollback. | Mark `rollback_failed`; escalate to user attention (axiom 06 line 136). |
| `EXTERNAL_SYNC_FAILED` | Partial-failure terminal: some events confirmed missing, no auto-retry. | Manual retry via `reconcile_after_crash`. |

The eleven codes above are declared in
`backend/src/agentic_calendar/contracts/reason_codes.py` alongside the existing
Phase 1 codes.

## Related Docs

- `05-scheduler-policy.md`
- `13-concurrency-model.md`
- `16-reliability-patterns.md`
- `../specs/approval-event.schema.md`
- `../specs/calendar-event-mapping.schema.md`
- `../specs/draft-schedule.schema.md`
- `../specs/calendar-reconciliation.schema.md`
- `../decisions/ADR-0002-preview-only-calendar-writes.md`
