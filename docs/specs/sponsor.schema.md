# Sponsor Schema

## Owner

Sponsor invite flow and Accountability Contract Manager.

## Consumers

Sponsor Report Generator (`../axioms/21-accountability-layer.md`), Sponsor Report Delivery Service, Notification Layer.

## Purpose

Represent a single trusted third party (parent, mentor, coach) who may receive
permissioned progress reports for one user. The sponsor row is the deterministic
record of *who* may receive reports and *whether the relationship is currently
active*. It is kept separate from the `motivation_profile`, which records the
user's chosen `sponsor_visibility_level`; the sponsor row records the
relationship lifecycle (invited, accepted, revoked).

Sponsor reporting is opt-in, explicit, and revocable (`21-accountability-layer.md`).
No sponsor report may be generated or delivered unless a sponsor row exists in
`accepted` status **and** the user's `motivation_profile` has `sponsor_enabled:
true` with a non-`none` `sponsor_visibility_level` pointing at this `sponsor_id`.

## Privacy Note On Sponsor Identity

Do not store free-text personal data about the sponsor beyond what is needed to
deliver a report. The MVP stores a coarse `relationship` label and a
`contact_channel`; it does **not** store the sponsor's raw name, email body,
phone number, or notes in this contract. Channel-specific delivery addresses are
resolved by the Notification Layer from a separate secured store and are never
copied into sponsor reports.

## JSON Example

```json
{
  "sponsor_id": "sponsor_001",
  "user_id": "user_123",
  "relationship": "parent",
  "contact_channel": "email",
  "status": "accepted",
  "invited_at": "2026-04-28T12:00:00-07:00",
  "accepted_at": "2026-04-28T18:30:00-07:00",
  "revoked_at": null,
  "created_at": "2026-04-28T12:00:00-07:00",
  "updated_at": "2026-04-28T18:30:00-07:00"
}
```

## Field Definitions

| Field | Type | Purpose |
| --- | --- | --- |
| `sponsor_id` | string | Primary key; referenced by `motivation_profile.sponsor_id`. |
| `user_id` | string | The user whose progress this sponsor may see. |
| `relationship` | enum: `parent`, `mentor`, `coach`, `peer`, `other` | Coarse relationship label; never free-text identity. |
| `contact_channel` | enum: `in_app`, `email`, `push` | Delivery channel for reports. |
| `status` | enum: `pending`, `accepted`, `revoked` | Invite lifecycle state. |
| `invited_at` | datetime | When the invite was created. |
| `accepted_at` | datetime or null | When the user accepted; required iff `status` is `accepted`. |
| `revoked_at` | datetime or null | When the user revoked; required iff `status` is `revoked`. |
| `created_at` | datetime | Row creation time. |
| `updated_at` | datetime | Last lifecycle transition time. |

## Invite Lifecycle

The status field is a deterministic state machine. The only allowed transitions
are:

- `pending → accepted` (explicit user acceptance; sets `accepted_at`).
- `pending → revoked` (user declines before accepting; sets `revoked_at`).
- `accepted → revoked` (user revokes an active sponsor; sets `revoked_at`).

`revoked` is terminal. A revoked sponsor is never reactivated; the user invites a
new sponsor row instead. Re-deriving any status from LLM prose is forbidden.

Revocation takes effect **before the next generated report** and must not break
the user's active plan (`21-accountability-layer.md`).

## Required Fields

- `sponsor_id`
- `user_id`
- `relationship`
- `contact_channel`
- `status`
- `invited_at`
- `created_at`
- `updated_at`

Conditionally required:

- `accepted_at` is required when `status` is `accepted` and forbidden otherwise.
- `revoked_at` is required when `status` is `revoked` and forbidden otherwise.

## Validation Rules

- All timestamps must be timezone-aware.
- `updated_at` must not precede `created_at`.
- `accepted_at`, when present, must not precede `invited_at`.
- `revoked_at`, when present, must not precede `invited_at`.
- `status: accepted` requires a non-null `accepted_at` and a null `revoked_at`.
- `status: revoked` requires a non-null `revoked_at`.
- `status: pending` requires both `accepted_at` and `revoked_at` to be null.

## Invalid Examples

```json
{ "status": "accepted", "accepted_at": null }
```

Reason: accepted status without an `accepted_at` timestamp.

```json
{ "status": "pending", "accepted_at": "2026-04-28T18:30:00-07:00" }
```

Reason: a pending invite must not carry an acceptance timestamp.

```json
{ "status": "revoked", "revoked_at": null }
```

Reason: revoked status without a `revoked_at` timestamp.

## Relationships

- `motivation_profile.sponsor_id` references this row.
- The Sponsor Report Generator reads `status` (must be `accepted`) before
  producing any report.
- The Sponsor Report Delivery Service reads `contact_channel`.

## Related Docs

- `motivation-profile.schema.md`
- `sponsor-report.schema.md`
- `notification-log.schema.md`
- `../axioms/21-accountability-layer.md`
- `../axioms/01-system-boundaries.md`
