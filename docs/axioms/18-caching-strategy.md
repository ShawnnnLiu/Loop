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

For the `task_template` target, the intended convention is that `object_schema_version` carries the `template_schema_version` of the `MilestoneTemplate` (the `templates/` registry) behind the entry. No production caller assembles `task_template` cache entries yet — that composition root is future work, the same way the `rag_retrieval` / `syllabus_units` producers are deferred — but following this convention makes the "Template schema update" trigger in the table above mechanical: bumping `TEMPLATE_SCHEMA_VERSION` changes the key and forces regeneration. The linkage is pinned in `backend/tests/templates/test_registry.py`.

## Cost Implication

Caching reduces LLM cost on stable role targets. Combined with the limits in `09-cost-and-metrics.md`, caching is a primary lever to keep LLM-only cost near the ~$0.40 per active user per month target.

## What Not to Cache

- User profiles. They change frequently and contain personal data.
- Full draft schedules. They are derived from many shifting inputs.
- Telemetry. It must be append-only and tied to identifying metadata.
- Source claims with expired `expires_at`.

## Phase 5 Implementation

The MVP realizes this in the `cache/` leaf kernel:

- **Keys** (`cache/keys.py`): `CacheKey` carries exactly the dimensions above —
  `target`, `role_target`, `company_target`, `freshness_window`,
  `claim_version_set`, and the cached object's `object_schema_version` — plus a
  `cache_schema_version` for the key format itself. Keys are byte-stable: the
  claim set is sorted/de-duplicated and string dimensions normalised, so requests
  differing only in claim order or casing collide. The freshness window is a
  `YYYY-MM` month bucket derived from the injected clock. `fingerprint()` reuses
  `contracts/hashing.canonical_mapping_hash` rather than inventing a hash.
- **Cached units**: both the resolved source-claim set (`rag_retrieval`) and the
  generated syllabus (`syllabus_units`) are cacheable behind one store, so a
  stable `(role, company, freshness, claims)` reuses prior LLM work.
- **Invalidation follows evidence** (`cache/invalidation.py`): each entry records
  the `source_claim_ids` that justify it; `is_entry_valid` treats an entry as
  stale when any referenced claim is missing, expired, or contradicted. The
  composition root treats a stale hit as a miss. `now` always comes from the
  injected clock.
- **Company context**: a `CompanyTarget` (name + trusted careers/eng-blog
  domains) feeds both the `company_target` key dimension and the source-claim
  classifier's company context (axiom 08) from one place. Domains are declared
  explicitly, never guessed from the company name.

The store is in-memory only in the MVP (no Redis/persistence).

## Related Docs

- `08-rag-source-claims.md`
- `09-cost-and-metrics.md`
- `../specs/source-claim.schema.md`
