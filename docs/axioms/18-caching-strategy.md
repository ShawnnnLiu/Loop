# 18: Caching Strategy

## Principle

Cache stable, reusable units of work. Do not cache full per-user generated plans; users differ in too many dimensions for full-profile caching to be useful.

## Do Not Prioritize Full-Profile Caching

Full-profile cache hits are rare. Two users may both prepare for backend SWE interviews but differ in timeline, target companies, availability, weaknesses, and experience level. Caching by profile fingerprint produces low hit rates and stale plans.

## Better Cache Targets

Prioritize caching:

- Company interview patterns.
- Topic learning modules.
- RAG retrieval results.
- Canonical task templates.
- Skill-to-curriculum mappings.

These objects are more stable and reusable than full generated plans.

## Cache Invalidation

| Cache Type | Invalidation Trigger |
| --- | --- |
| Company interview pattern | Source claim expiration or contradiction |
| Topic module | Curriculum version update |
| RAG retrieval result | Claim expiration |
| Task template | Template schema update |
| Skill-to-curriculum mapping | Major taxonomy update |

Cache entries must reference the source claims that justify them so invalidation can follow expiration.

## Cache Keys

Recommended cache key dimensions:

- Role target.
- Company target.
- Freshness window (date range).
- Source claim version set.
- Schema version.

Cache keys must include the schema version of the cached object so a contract change forces re-generation.

## Cost Implication

Caching reduces LLM cost on stable role targets. Combined with the limits in `09-cost-and-metrics.md`, caching is a primary lever to keep LLM-only cost near the ~$0.40 per active user per month target.

## What Not to Cache

- User profiles. They change frequently and contain personal data.
- Full draft schedules. They are derived from many shifting inputs.
- Telemetry. It must be append-only and tied to identifying metadata.
- Source claims with expired `expires_at`.

## Related Docs

- `08-rag-source-claims.md`
- `09-cost-and-metrics.md`
- `../specs/source-claim.schema.md`
