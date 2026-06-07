# Cache Entry Schema

## Owner

The `cache/` leaf kernel (Phase 5b, axiom 18).

## Consumers

`InMemoryCache` (stores one entry per `CacheKey.fingerprint()`) and
`cache/invalidation.py` (treats an entry as stale when any justifying claim is
missing, expired, or contradicted).

## Purpose

One cached value plus the evidence that justifies it. Each entry records the
`source_claim_ids` behind it so invalidation can follow claim
expiration/contradiction.

## JSON Example

```json
{
  "key": {
    "target": "syllabus_units",
    "role_target": "backend swe",
    "freshness_window": "2026-06",
    "object_schema_version": "syl-v1"
  },
  "value_kind": "syllabus_units",
  "value_json": { "modules": [] },
  "source_claim_ids": ["claim_1"],
  "created_at": "2026-06-04T12:00:00+00:00"
}
```

## Field Semantics

| Field | Purpose |
| --- | --- |
| `key` | The `CacheKey` this entry is stored under (see `cache-key.schema.md`) |
| `value_kind` | The cached unit kind; must equal `key.target` |
| `value_json` | The cached payload (must be JSON-serializable) |
| `source_claim_ids` | The claims that justify the entry, for invalidation (default `[]`) |
| `created_at` | Timezone-aware creation instant |

## Invariants

- `value_kind` must equal `key.target`.
- `created_at` must be timezone-aware.
- `value_json` must be JSON-serializable (enforced at `put` time by the store).
- Unknown fields are rejected (`extra="forbid"`).

## Invalid Examples

```json
{ "key": { "target": "syllabus_units", "...": "..." }, "value_kind": "rag_retrieval", "value_json": {}, "created_at": "2026-06-04T12:00:00+00:00" }
```

Reason: `value_kind` must match `key.target`.

```json
{ "key": { "...": "..." }, "value_kind": "syllabus_units", "value_json": {}, "created_at": "2026-06-04T12:00:00" }
```

Reason: `created_at` must be timezone-aware.

## Related Docs

- `../axioms/18-caching-strategy.md`
- `cache-key.schema.md`
- `source-claim.schema.md`
