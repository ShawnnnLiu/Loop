# Consent Record Schema

## Owner

Consent service (`consent/` region; ADR-0007).

## Consumers

Pooled-duration training (Phase 6b), pooled serving fallback chain (Phase 6b),
cohort retrieval (Phase 6d), data-control CLIs, data-access audit log.

## Purpose

A `ConsentRecord` is the deterministic, auditable record that one user granted
(or has since revoked) one explicit data-use scope. Axiom 07 forbids
cross-user training data without opt-in; this record **is** the opt-in. No
pooled-training read, pooled-serving lookup, or cohort-retrieval read may
proceed without an active (`granted`) record for the matching scope —
enforced by the consent gate at training time **and** serving time.

A record is created in `granted` status by the explicit user action of
granting; the record is the grant. Revocation is a lifecycle transition, not
a deletion, so the consent history stays auditable. Re-consent after
revocation is a **new record**, never a reactivation of the revoked row.

## JSON Example

```json
{
  "consent_record_id": "consent_001",
  "user_id": "user_123",
  "scope": "pooled_training",
  "status": "granted",
  "consent_version": "2026-06",
  "granted_at": "2026-06-10T09:00:00-07:00",
  "revoked_at": null,
  "created_at": "2026-06-10T09:00:00-07:00",
  "updated_at": "2026-06-10T09:00:00-07:00"
}
```

## Field Definitions

| Field | Type | Purpose |
| --- | --- | --- |
| `consent_record_id` | string | Primary key. |
| `user_id` | string | The user who granted this scope. |
| `scope` | enum: `pooled_training`, `cohort_retrieval` | The single data-use this record covers. One record covers exactly one scope; consenting to both scopes produces two records. |
| `status` | enum: `granted`, `revoked` | Lifecycle state. |
| `consent_version` | string | Version label of the consent language the user agreed to. A new consent-language version requires a fresh grant; an active record for an older version does not cover the new terms. |
| `granted_at` | datetime | When the user granted. Always present — a record only exists because a grant happened. |
| `revoked_at` | datetime or null | When the user revoked; required iff `status` is `revoked`. |
| `created_at` | datetime | Row creation time. |
| `updated_at` | datetime | Last lifecycle transition time. |

## Lifecycle

The status field is a deterministic state machine. The only allowed
transition is:

- `granted → revoked` (explicit user revocation; sets `revoked_at`).

`revoked` is terminal. Re-consent creates a new record with a new
`consent_record_id`. At most one record per `(user_id, scope)` may be in
`granted` status at a time; the consent store enforces this. Deriving consent
state from LLM prose, chat history, or any free-text surface is forbidden.

Revocation takes effect immediately: the next consent-gate check — training
or serving — sees `revoked` and denies with `CONSENT_REVOKED`. Events from a
revoked user must be absent from the next pooled artifact build.

## Required Fields

- `consent_record_id`
- `user_id`
- `scope`
- `status`
- `consent_version`
- `granted_at`
- `created_at`
- `updated_at`

Conditionally required:

- `revoked_at` is required when `status` is `revoked` and forbidden otherwise.

## Validation Rules

- All timestamps must be timezone-aware.
- `updated_at` must not precede `created_at`.
- `revoked_at`, when present, must not precede `granted_at`.
- `status: granted` requires a null `revoked_at`.
- `status: revoked` requires a non-null `revoked_at`.
- No free-text fields: `scope` and `status` are closed enums and
  `consent_version` is a version label, never user prose.

## Invalid Examples

```json
{ "status": "granted", "revoked_at": "2026-06-10T10:00:00-07:00" }
```

Reason: a granted record must not carry a revocation timestamp.

```json
{ "status": "revoked", "revoked_at": null }
```

Reason: revoked status without a `revoked_at` timestamp.

```json
{ "scope": "marketing_email" }
```

Reason: scope outside the closed enum.

## Relationships

- The consent gate (`consent/gate.py`) resolves the active record per
  `(user_id, scope)` and writes one `data_access_audit` entry per check.
- Pooled training (Phase 6b) receives the consented user-id set from the
  composition root; non-consented users' events never enter the artifact.
- Cohort retrieval (Phase 6d) requires an active `cohort_retrieval` record.

## Related Docs

- `data-access-audit.schema.md`
- `telemetry.schema.md`
- `../axioms/07-telemetry-and-drift.md`
- `../axioms/17-duration-estimation.md`
- `../decisions/ADR-0007-consent-gated-deterministic-pooled-personalization.md`
