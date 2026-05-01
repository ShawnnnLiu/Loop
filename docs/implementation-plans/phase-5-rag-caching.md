# Phase 5: RAG Quality and Caching

## Goal

Add auditable source claims, deterministic confidence scoring, expiration, and caching so syllabus generation uses stable evidence instead of raw retrieved prose.

## Required Docs

- `../../AGENTS.md`
- `../axioms/08-rag-source-claims.md`
- `../axioms/09-cost-and-metrics.md`
- `../specs/source-claim.schema.md`
- `../specs/syllabus-units.schema.md`
- `../decisions/ADR-0005-structured-syllabus-not-prose.md`

## Deliverables

- Source claim ingestion and normalization.
- Source type classification.
- Deterministic confidence scoring.
- Claim expiration policy.
- Cache keys for role target, company target, and freshness window.
- Syllabus generation inputs that reference claim IDs.
- Admissions / application milestone templates (for college, graduate, and career-transition goals).

## Acceptance Criteria

- LLMs do not assign source confidence.
- Confidence scores follow the documented formula and clamp to `[0, 1]`.
- Expired claims do not drive new syllabus generation unless refreshed.
- Syllabus units reference valid `source_claim_ids`.
- Cache hits reduce repeated LLM work for stable role targets.

## Explicit Non-Goals

- Full web-scale crawler.
- User-specific model training.
- Unverified anecdote-driven syllabus generation.
- Treating raw prose as the durable syllabus contract.

## Test Expectations

- Confidence formula tests for every source type.
- Expiration tests.
- Corroboration and contradiction adjustment tests.
- Cache key tests.
- Syllabus validation tests for missing or expired source claims.
