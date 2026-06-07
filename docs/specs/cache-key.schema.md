# Cache Key Schema

## Owner

The `cache/` leaf kernel (Phase 5b, axiom 18).

## Consumers

The cache store (`InMemoryCache` keys entries by `CacheKey.fingerprint()`) and
any composition root that reads/writes cached units of work.

## Purpose

An auditable, byte-stable identity for a cached unit of work. Its dimensions are
exactly axiom 18's: role target, company target, freshness window, the
source-claim version set, and the *schema version of the cached object* — plus a
`cache_schema_version` for the key format itself. Keys are byte-stable: the claim
set is sorted/de-duplicated and string dimensions are normalised, so requests
differing only in claim order or casing collide.

## JSON Example

```json
{
  "target": "syllabus_units",
  "role_target": "backend swe",
  "company_target": "stripe",
  "freshness_window": "2026-06",
  "claim_version_set": ["a", "b"],
  "object_schema_version": "syl-v1",
  "cache_schema_version": "cache-key-v1"
}
```

## Field Semantics

| Field | Purpose |
| --- | --- |
| `target` | The kind of cached unit (`CacheTarget`; see below) |
| `role_target` | Normalised (stripped/casefolded) role dimension (non-empty) |
| `company_target` | Normalised company dimension (default `""`) |
| `freshness_window` | `YYYY-MM` month bucket derived from the injected clock (non-empty) |
| `claim_version_set` | Sorted, de-duplicated source-claim id set (default `[]`) |
| `object_schema_version` | Schema version of the cached object; a contract change forces a miss (non-empty) |
| `cache_schema_version` | Key-format version; a bump invalidates every key (default `cache-key-v1`) |

## Allowed `target` Values

`company_interview_pattern`, `topic_module`, `rag_retrieval`, `task_template`,
`skill_to_curriculum`, `syllabus_units`.

For `task_template`, `object_schema_version` carries the
`MilestoneTemplate.template_schema_version` (see `milestone-template.schema.md`).

## Invariants

- `role_target`, `freshness_window`, and `object_schema_version` are non-empty.
- `target` is a known `CacheTarget`.
- Unknown fields are rejected (`extra="forbid"`).

## Invalid Examples

```json
{ "target": "syllabus_units", "role_target": "", "freshness_window": "2026-06", "object_schema_version": "syl-v1" }
```

Reason: `role_target` must be non-empty.

```json
{ "target": "not_a_target", "role_target": "x", "freshness_window": "2026-06", "object_schema_version": "v1" }
```

Reason: unknown `target`.

## Related Docs

- `../axioms/18-caching-strategy.md`
- `cache-entry.schema.md`
- `milestone-template.schema.md`
