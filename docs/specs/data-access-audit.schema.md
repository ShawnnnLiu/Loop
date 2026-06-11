# Data Access Audit Schema

## Owner

Consent service (`consent/` region; ADR-0007).

## Consumers

Engineering review, privacy metrics, data-control CLIs, pooled-training and
cohort-retrieval pipelines (Phase 6b/6d callers observe their own outcomes).

## Purpose

A `DataAccessAuditEntry` is the append-only audit record for every
consent-scoped data access and every user data-control operation. ADR-0007
requires that pooled training, pooled serving, and cohort retrieval are
auditable, and that view/export/delete leave a trail. Every consent-gate
check writes exactly one entry — allowed or denied — and every data-control
operation writes one entry, so "who touched whose data, why, and with what
outcome" is always answerable from this log alone.

The log stores identifiers and outcome metadata only. It must never contain
telemetry payloads, task content, calendar text, or any other user data, and
it has no free-text fields.

Audit entries are retained even after a user's data is deleted: the
`DATA_DELETED` entry is the proof the deletion happened. Deleting the audit
trail along with the data would erase that proof.

## JSON Example

```json
{
  "audit_entry_id": "audit_001",
  "user_id": "user_123",
  "purpose": "pooled_training",
  "accessor": "training_pipeline",
  "outcome": "denied",
  "reason_code": "CONSENT_REVOKED",
  "created_at": "2026-06-10T09:30:00-07:00"
}
```

## Field Definitions

| Field | Type | Purpose |
| --- | --- | --- |
| `audit_entry_id` | string | Primary key; unique, used for dedup. |
| `user_id` | string | The user whose data was accessed (or whose access was denied). |
| `purpose` | enum, see below | Why the data was touched. |
| `accessor` | enum: `operator_cli`, `training_pipeline`, `serving_pipeline`, `retrieval_pipeline` | Which system component performed the access. Never a person's identity. |
| `outcome` | enum: `allowed`, `denied` | Whether the access proceeded. |
| `reason_code` | enum `ReasonCode` or null | Typed outcome code; see semantics below. |
| `created_at` | datetime | When the access resolved. |

## Allowed `purpose` Values

| Purpose | Meaning | Consent scope consulted |
| --- | --- | --- |
| `pooled_training` | The user's telemetry was read (or refused) for a pooled artifact build. | `pooled_training` |
| `pooled_serving` | A consent-scoped serving lookup consulted the user's standing (Phase 6b fallback chain). | `pooled_training` |
| `cohort_retrieval` | The user's cohort assignment fed retrieval ranking (Phase 6d). | `cohort_retrieval` |
| `data_view` | The user's data was listed via the data-control CLI. | none — a user always may view their own data |
| `data_export` | The user's data was exported as JSON. | none |
| `data_delete` | The user's data was deleted from registered stores. | none |

The consent scope is derivable from the purpose, so it is not stored
separately.

## `reason_code` Semantics

| Case | `reason_code` |
| --- | --- |
| `outcome: denied` | required; `CONSENT_MISSING` (no record for the scope, or no record for the current consent version) or `CONSENT_REVOKED` (the latest record for the scope is revoked). |
| `outcome: allowed`, `purpose: data_export` | required; exactly `DATA_EXPORTED`. |
| `outcome: allowed`, `purpose: data_delete` | required; exactly `DATA_DELETED`. |
| `outcome: allowed`, any other purpose | must be null. |

## Required Fields

- `audit_entry_id`
- `user_id`
- `purpose`
- `accessor`
- `outcome`
- `created_at`

`reason_code` is conditionally required per the semantics table above.

## Validation Rules

- `created_at` must be timezone-aware.
- `outcome: denied` requires `reason_code` to be `CONSENT_MISSING` or
  `CONSENT_REVOKED`.
- `outcome: allowed` with `purpose: data_export` requires `reason_code:
  DATA_EXPORTED`; with `purpose: data_delete` requires `reason_code:
  DATA_DELETED`; with any other purpose requires a null `reason_code`.
- Data-control purposes (`data_view`, `data_export`, `data_delete`) are never
  denied by the consent gate (a user always controls their own data), so a
  `denied` outcome with a data-control purpose is invalid.
- Entries are append-only: an `audit_entry_id` is written exactly once and
  never edited.

## Invalid Examples

```json
{ "outcome": "denied", "reason_code": null }
```

Reason: a denied access must carry a typed consent reason code.

```json
{ "outcome": "allowed", "purpose": "pooled_training", "reason_code": "DATA_EXPORTED" }
```

Reason: an allowed training read carries no reason code.

```json
{ "outcome": "allowed", "purpose": "data_delete", "reason_code": null }
```

Reason: a completed deletion must be marked `DATA_DELETED`.

```json
{ "outcome": "denied", "purpose": "data_view", "reason_code": "CONSENT_MISSING" }
```

Reason: data controls are never consent-denied.

## Relationships

- The consent gate (`consent/gate.py`) writes one entry per check.
- The data-control functions (`consent/data_controls.py`) write one entry per
  view/export/delete operation.
- `reason_code` values are members of the system-wide `ReasonCode` enum
  (axiom 16; consent codes defined by this spec and
  `consent-record.schema.md` per axiom 16's "other reason codes are defined
  in specs" note).

## Related Docs

- `consent-record.schema.md`
- `notification-log.schema.md`
- `../axioms/07-telemetry-and-drift.md`
- `../axioms/16-reliability-patterns.md`
- `../decisions/ADR-0007-consent-gated-deterministic-pooled-personalization.md`
