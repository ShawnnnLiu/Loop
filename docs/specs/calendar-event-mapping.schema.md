# Calendar Event Mapping Schema

## Owner

Calendar Write Manager.

## Consumers

Calendar verifier, rollback flow, telemetry, audit log.

## Purpose

Local mapping between an internal task and the external calendar event the system created on the user's behalf. Verification, duplicate prevention, and rollback all rely on this mapping.

## JSON Example

```json
{
  "task_id": "dp_002",
  "plan_version": "plan_004",
  "run_id": "run_2026_05_04_001",
  "calendar_event_id": "gcal_evt_abc123",
  "scheduled_start": "2026-05-06T19:00:00-07:00",
  "scheduled_end": "2026-05-06T20:30:00-07:00",
  "calendar_write_status": "verified",
  "user_modified_bool": false,
  "last_verified_at": "2026-05-04T18:16:00-07:00"
}
```

## Required Fields

- `task_id`
- `plan_version`
- `run_id`
- `calendar_event_id`
- `scheduled_start`
- `scheduled_end`
- `calendar_write_status`
- `user_modified_bool`
- `last_verified_at`

## Allowed `calendar_write_status` Values

- `dry_run`
- `written`
- `verified`
- `verification_failed`
- `rollback_pending`
- `rolled_back`
- `rollback_failed`

## Calendar Event Metadata

The Calendar Write Manager must attach app-level metadata to each external event so duplicates can be detected and rollback can succeed without title matching:

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

## Invariants

- Mapping is created only by Calendar Write Manager.
- Verified mappings must include a non-null `calendar_event_id`.
- `scheduled_start` must be earlier than `scheduled_end`.
- Rollback uses `calendar_event_id` and metadata, not title matching.
- Duplicate prevention checks existing mappings and external metadata before creating events.
- `user_modified_bool: true` mappings must preserve the user's edits and not be overwritten silently.

## Invalid Examples

```json
{
  "task_id": "dp_002",
  "calendar_event_id": null,
  "calendar_write_status": "verified"
}
```

Reason: verified mapping lacks external event ID.

```json
{
  "task_id": "dp_002",
  "calendar_write_status": "done"
}
```

Reason: invalid status enum.

```json
{
  "task_id": "dp_002",
  "scheduled_start": "2026-05-06T20:30:00-07:00",
  "scheduled_end": "2026-05-06T19:00:00-07:00",
  "calendar_write_status": "written"
}
```

Reason: end before start.

## Related Docs

- `../axioms/06-calendar-safety.md`
- `../axioms/13-concurrency-model.md`
- `approval-event.schema.md`
- `telemetry.schema.md`
