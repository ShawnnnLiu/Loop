# Approval Event Schema

## Owner

Approval UI and approval service.

## Consumers

Calendar Write Manager, audit log, Supervisor.

## Purpose

Capture the explicit user authorization for a specific draft schedule and hashed payload. Calendar writes are forbidden without a matching `approval_event` whose hash check passes at write time.

## JSON Example

```json
{
  "approval_event_id": "approval_123",
  "user_id": "user_123",
  "plan_id": "plan_004",
  "draft_schedule_id": "draft_002",
  "action_type": "add_to_calendar",
  "approved_payload_hash": "sha256:abc123...",
  "hash_algorithm": "sha256",
  "hash_canonicalization_version": "v1",
  "created_at": "2026-05-04T17:55:00-07:00",
  "expires_at": "2026-05-05T17:55:00-07:00"
}
```

## Field Semantics

| Field | Purpose |
| --- | --- |
| `approval_event_id` | Stable identifier referenced by Calendar Write Manager |
| `user_id` | Approving user |
| `plan_id` | Plan version being approved |
| `draft_schedule_id` | Draft schedule being approved |
| `action_type` | One of the approved action types (see below) |
| `approved_payload_hash` | Hash of the canonicalized payload the user saw |
| `hash_algorithm` | Hash algorithm used; `sha256` for the MVP |
| `hash_canonicalization_version` | Canonicalization version that produced the hash |
| `created_at` | Approval timestamp in the user's timezone |
| `expires_at` | Time at which the approval is no longer honored (default 24 hours) |

## Allowed `action_type` Values

- `add_to_calendar`
- `update_calendar` (for replans)
- `rollback_calendar`

Other action types must be explicitly defined before use.

## Allowed `hash_algorithm` Values

- `sha256` (required for the MVP)

Future algorithms must be added explicitly. The Calendar Write Manager must reject any unknown algorithm.

## Hash Coverage

The `approved_payload_hash` is computed over the canonical serialization of the draft schedule. See `../axioms/06-calendar-safety.md` for the exact protocol.

The hash **must cover**:

- All `task_id` values in scheduled order.
- All `start` and `end` timestamps.
- All `calendar_event_status` flags.
- The `plan_version` ID.
- The `draft_schedule_id`.

The hash **must not cover** UI metadata, non-scheduling fields, or unrelated server timestamps.

## Mandatory Write-Time Hash Check

Before any external calendar API call, Calendar Write Manager must:

1. Re-fetch the draft schedule.
2. Recompute the payload hash using the algorithm and canonicalization version recorded on this approval.
3. Compare to `approved_payload_hash`.
4. If mismatch, abort the write, log `APPROVAL_HASH_MISMATCH`, and surface the user-facing message: "The plan changed after you approved it. Please review and re-approve."
5. If match, proceed.

## Time-Based Invalidation

Approval events expire after **24 hours** by default. After `expires_at`, the hash check is skipped because the user must re-approve regardless. Expired approvals must not be honored under any condition.

## Invariants

- Calendar writes require an `approval_event_id`.
- The recorded `approved_payload_hash` must match the payload being written, recomputed under the recorded `hash_canonicalization_version`.
- An approval applies to one `plan_id` and one `draft_schedule_id`.
- Rejections must be stored as separate events and must not authorize writes.
- Approval records are immutable once created. New approvals must produce new `approval_event_id` values.
- `expires_at` must be after `created_at`.
- `hash_algorithm` must be one of the allowed values.
- Hash mismatches at write time are P1 incidents and must produce a typed `reason_code` of `APPROVAL_HASH_MISMATCH`.

## Audit Logging

Every hash check (pass, mismatch, expired) is logged with:

- `approval_event_id`
- recomputed hash
- approved hash
- result

Hash mismatches are flagged as P1 incidents because they indicate either a bug or a security issue.

## Invariant

**No `approval_event_id` and no matching hash → no calendar write.** Both checks happen immediately before any external API call.

## Invalid Examples

```json
{ "action_type": "add_to_calendar", "approved_payload_hash": null }
```

Reason: approved payload hash is required.

```json
{
  "approval_event_id": "approval_1",
  "approved_payload_hash": "abc",
  "hash_algorithm": "md5"
}
```

Reason: unsupported hash algorithm.

```json
{
  "approval_event_id": "approval_1",
  "approved_payload_hash": "sha256:...",
  "hash_canonicalization_version": null
}
```

Reason: missing canonicalization version; the hash cannot be revalidated.

```json
{
  "approval_event_id": "approval_1",
  "created_at": "2026-05-04T17:55:00-07:00",
  "expires_at": "2026-05-04T17:00:00-07:00"
}
```

Reason: expiry before creation.

## Related Docs

- `../axioms/06-calendar-safety.md`
- `../axioms/13-concurrency-model.md`
- `scheduler-output.schema.md`
- `calendar-event-mapping.schema.md`
- `../decisions/ADR-0002-preview-only-calendar-writes.md`
