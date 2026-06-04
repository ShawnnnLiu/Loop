# Notification Log Schema

## Owner

Sponsor Report Delivery Service (`../axioms/21-accountability-layer.md`).

## Consumers

Audit log, metrics (Phase 4 sponsor opt-in / delivery rates), engineering review.

## Purpose

`NotificationLog` is the append-only audit record for every sponsor report
delivery attempt — drafted, approved, sent, blocked, dry-run, or failed. Axiom
21 requires that "report generation, approval, and delivery are logged," and the
Phase 3 acceptance criteria require that "every sponsor report delivery is logged
with `report_id`, `sponsor_id`, `visibility_level`, and status." This schema is
that record.

A log entry is written for **every** terminal outcome, including blocked
attempts (`SPONSOR_PERMISSION_MISSING`, `SPONSOR_VISIBILITY_VIOLATION`,
`USER_APPROVAL_REQUIRED`). A blocked privacy violation additionally sets
`engineering_review: true` (golden scenario 19).

## Dry-Run And Side-Effect Safety

Sending a sponsor report is an external side effect, so the delivery path
supports `dry_run` (axiom: every external side effect must support dry-run and
verification). A dry-run produces a log with `status: dry_run` and performs no
delivery. Unlike a calendar write, a delivered notification cannot be recalled,
so there is no rollback status; integrity is enforced *before* send by the
approved-payload-hash recheck rather than after.

## JSON Example

```json
{
  "notification_log_id": "notif_001",
  "report_id": "report_123",
  "sponsor_id": "sponsor_001",
  "user_id": "user_123",
  "visibility_level": "summary_only",
  "channel": "email",
  "status": "sent",
  "reason_code": null,
  "engineering_review": false,
  "dry_run": false,
  "created_at": "2026-05-10T19:12:00-07:00"
}
```

## Field Definitions

| Field | Type | Purpose |
| --- | --- | --- |
| `notification_log_id` | string | Primary key; unique, used for dedup. |
| `report_id` | string | The sponsor report this attempt refers to. |
| `sponsor_id` | string | Recipient sponsor row. |
| `user_id` | string | Subject of the report. |
| `visibility_level` | enum `SponsorVisibility` | Level the report was filtered to. |
| `channel` | enum: `in_app`, `email`, `push` | Delivery channel attempted. |
| `status` | enum: `drafted`, `approved`, `sent`, `dry_run`, `blocked`, `failed` | Terminal outcome of the attempt. |
| `reason_code` | enum `ReasonCode` or null | Set when `status` is `blocked` or `failed`; null on success. |
| `engineering_review` | boolean | True when a privacy violation requires engineering follow-up. |
| `dry_run` | boolean | True when no real delivery occurred. |
| `created_at` | datetime | When the attempt resolved. |

## Status Semantics

| Status | Meaning | `reason_code` |
| --- | --- | --- |
| `drafted` | Report draft created, not yet approved. | null |
| `approved` | User approved the draft for send. | null |
| `sent` | Report delivered to the channel. | null |
| `dry_run` | Delivery simulated; nothing sent. | null |
| `blocked` | Permission, visibility, or approval gate failed. | required |
| `failed` | Channel delivery raised after approval. | required |

## Required Fields

- `notification_log_id`
- `report_id`
- `sponsor_id`
- `user_id`
- `visibility_level`
- `channel`
- `status`
- `dry_run`
- `created_at`

`reason_code` is required when `status` is `blocked` or `failed`, and must be
null otherwise.

## Validation Rules

- `created_at` must be timezone-aware.
- `reason_code` is non-null iff `status` is `blocked` or `failed`.
- `visibility_level` may be `none` only on a `blocked` entry whose
  `reason_code` is `SPONSOR_PERMISSION_MISSING` (the no-permission path).
- `engineering_review` is true only on `blocked` entries.

## Privacy Rule

The log stores identifiers and outcome metadata only. It must **not** contain
report body content, milestone names, calendar titles, or any denylisted field
from `sponsor-report.schema.md`.

## Invalid Examples

```json
{ "status": "sent", "reason_code": "SPONSOR_VISIBILITY_VIOLATION" }
```

Reason: a successful send must not carry a failure reason code.

```json
{ "status": "blocked", "reason_code": null }
```

Reason: a blocked attempt must carry a reason code.

## Related Docs

- `sponsor.schema.md`
- `sponsor-report.schema.md`
- `../axioms/21-accountability-layer.md`
- `../axioms/06-calendar-safety.md`
- `../axioms/16-reliability-patterns.md`
