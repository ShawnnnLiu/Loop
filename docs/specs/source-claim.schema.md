# Source Claim Schema

## Owner

RAG ingestion pipeline and deterministic confidence scorer.

## Consumers

`StrategistNode`, syllabus validator, cache, audit views.

## Purpose

Every retrieved claim becomes an auditable object with provenance, source type, deterministic confidence, and expiration before it influences syllabus or task generation. LLMs must not assign confidence in the MVP.

## JSON Example

```json
{
  "claim_id": "claim_024",
  "claim_text": "Stripe backend interviews commonly emphasize API design and product-oriented engineering tradeoffs.",
  "source_url": "https://example.com/source",
  "source_type": "interview_report",
  "date_collected": "2026-04-28",
  "source_published_date": "2026-02-10",
  "confidence_score": 0.62,
  "confidence_bucket": "medium",
  "expires_at": "2026-07-28",
  "corroborating_claim_ids": ["claim_031", "claim_044"],
  "contradicting_claim_ids": []
}
```

## Field Semantics

| Field | Purpose |
| --- | --- |
| `claim_id` | Stable identifier for the claim |
| `claim_text` | Atomic, independently verifiable claim |
| `source_url` | Provenance link |
| `source_type` | Deterministic classification (see below) |
| `date_collected` | When the system retrieved or generated the claim |
| `source_published_date` | Publication date of the source, when available |
| `confidence_score` | Deterministic score in `[0, 1]` |
| `confidence_bucket` | `high`, `medium`, or `low` |
| `expires_at` | Effective expiry per source type |
| `corroborating_claim_ids` | Other claims that support this claim |
| `contradicting_claim_ids` | Other claims that conflict with this claim |

## Allowed `source_type` Values

- `official_job_posting`
- `company_engineering_blog`
- `role_taxonomy`
- `interview_postmortem`
- `interview_report`
- `personal_anecdote`
- `unclassified`

`source_type` must be classified by domain and URL rules, not by LLM judgment. See `../axioms/08-rag-source-claims.md`.

## Confidence Buckets

| Bucket | Score Range |
| --- | --- |
| `high` | >= 0.80 |
| `medium` | 0.55 – 0.79 |
| `low` | < 0.55 |

## Invariants

- `source_type` must be a known value from the list above.
- `confidence_score` is computed by the deterministic formula in `../axioms/08-rag-source-claims.md` and clamped to `[0, 1]`.
- `confidence_bucket` must be consistent with `confidence_score`.
- LLMs must not assign `confidence_score` or `confidence_bucket`.
- Expired claims must not drive new syllabus generation unless refreshed.
- Claims must be atomic enough to accept or reject independently.
- `corroborating_claim_ids` and `contradicting_claim_ids` reference existing `claim_id` values.

## Invalid Examples

```json
{
  "claim_text": "Study everything",
  "source_type": "blog",
  "confidence_score": 1.2
}
```

Reason: vague claim, invalid source type, score out of range.

```json
{
  "claim_id": "claim_1",
  "confidence_score": "high"
}
```

Reason: confidence must be numeric and deterministic.

```json
{
  "claim_id": "claim_2",
  "source_type": "interview_report",
  "confidence_score": 0.50,
  "confidence_bucket": "high"
}
```

Reason: bucket inconsistent with score.

## Related Docs

- `../axioms/08-rag-source-claims.md`
- `../axioms/18-caching-strategy.md`
- `syllabus-units.schema.md`
- `../implementation-plans/phase-5-rag-caching.md`
