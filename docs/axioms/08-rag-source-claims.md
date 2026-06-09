# 08: RAG and Source Claims

## Purpose

The retrieval system helps the Strategist generate company-aware and role-aware curricula. Retrieval must not be treated as ground truth. Every retrieved claim becomes an auditable `source_claim` with provenance, confidence, and expiration before it influences syllabus or task generation.

The corpus is not the moat. It is an input to the planning engine.

## Claim Schema Summary

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

See `../specs/source-claim.schema.md`.

## Deterministic Source Type Classification

Source type is classified by domain and URL rules, not by LLM judgment.

| Domain / Pattern | Source Type |
| --- | --- |
| Company careers domain | `official_job_posting` |
| Greenhouse / Lever / Ashby / Workday | `official_job_posting` |
| Company engineering blog | `company_engineering_blog` |
| levels.fyi | `role_taxonomy` |
| interviewing.io / Pramp | `interview_postmortem` |
| Glassdoor / Blind | `interview_report` |
| Personal blog | `personal_anecdote` |
| Unknown domain | `unclassified` |

## Deterministic Confidence Formula

```text
confidence_score =
  source_type_base_score
  + recency_bonus
  + corroboration_bonus
  - anecdotal_penalty
  - contradiction_penalty
  - stale_penalty
```

Scores are clamped to `[0, 1]`. LLMs must not assign confidence in the MVP.

### Base Scores

| Source Type | Base Score |
| --- | --- |
| `official_job_posting` | 0.90 |
| `company_engineering_blog` | 0.75 |
| `role_taxonomy` | 0.70 |
| `interview_postmortem` | 0.65 |
| `interview_report` | 0.50 |
| `personal_anecdote` | 0.35 |
| `unclassified` | 0.20 |

### Confidence Buckets

| Bucket | Score Range |
| --- | --- |
| `high` | >= 0.80 |
| `medium` | 0.55 – 0.79 |
| `low` | < 0.55 |

## Expiration Policy

| Source Type | Expiration |
| --- | --- |
| `official_job_posting` | 30 – 60 days or when posting closes |
| `interview_report` | 90 – 180 days |
| `role_taxonomy` | 180 days |
| `company_engineering_blog` | 365 – 730 days |
| `canonical_topic_module` | 2+ years |

Expired claims may be retained for audit history but must not drive new syllabus generation unless refreshed.

## Retrieval Quality Rules

The Strategist should prefer:

1. Official job postings.
2. Company engineering blogs.
3. Structured role taxonomies.
4. Corroborated interview reports.
5. Anecdotal reports only when labeled low confidence.

Low-confidence claims must not drive high-stakes curriculum decisions unless corroborated by higher-confidence claims.

## Confidence Formula Calibration

### Calibration Honesty

The base scores above are **initial priors derived from heuristic judgment, not from data**. They must be treated as tunable parameters subject to empirical validation, not as ground truth. Internal documentation, engineering reviews, and any user-facing surface that exposes confidence must describe these as heuristic priors until calibration is complete.

### Calibration Trigger

Calibration runs once the system has accumulated **>= 200 retrieved claims used in production plans**.

### Calibration Methodology

1. **Manual labeling pass.** A reviewer (initially the founder, later a labeler) tags a stratified sample of **100 claims** with one of these ground-truth quality labels:
   - `accurate_and_relevant`
   - `accurate_but_irrelevant`
   - `outdated`
   - `inaccurate`
   - `unverifiable`
2. **Score-vs-label analysis.** For each `source_type`, compute the distribution of ground-truth labels within each `confidence_bucket`. Adjust base scores so that:
   - `high` (>= 0.80) is **>= 85% `accurate_and_relevant`**.
   - `medium` (0.55–0.79) is **>= 60% `accurate_and_relevant`**.
   - `low` (< 0.55) is **excluded from high-stakes decisions**.
3. **Source-type re-weighting.** If a source type's empirical accuracy diverges from its base score by **> 0.15**, adjust the base score and record the change in a `confidence_calibration_log` table. Base scores must never be modified without a logged reason.
4. **Recency decay validation.** Re-evaluate decay rates by checking whether older claims actually correlate with worse accuracy. If a 90-day-old company blog is empirically as accurate as a 30-day-old one, slow the decay. If a 30-day-old interview report is already stale, accelerate it.

### Calibration Cadence

Recalibrate base scores:

- Quarterly, at minimum.
- Whenever a new `source_type` is added.
- Whenever a major source-class controversy occurs (for example, a heavily-cited blog turns out to be AI-generated slop).

### Calibration Log Schema

The `confidence_calibration_log` records every base-score change:

- `source_type`
- `prior_value`
- `new_value`
- `effective_at`
- `justification`
- `dataset_reference`
- `reviewer`

### Public-Facing Acknowledgment

No external claim of "accurate confidence scoring" or "calibrated source ranking" may be made until calibration is complete and a calibration log exists. MVP marketing and UI must describe confidence as heuristic.

## Heuristic Prior Magnitudes (Phase 5)

The formula structure, base scores, buckets, and expiration *ranges* above are
the durable policy. The concrete magnitudes of each bonus/penalty, the
recency/staleness time thresholds, and a single value inside each expiration
range are **implementation priors** chosen by heuristic judgment, not data. They
live in `backend/src/agentic_calendar/source_claims/priors.py` and, exactly like
the drift thresholds (axiom 07), are tunable parameters pending the calibration
pass — never presented as tuned. The Phase 5 defaults:

| Term | Default |
| --- | --- |
| `recency_bonus` | `+0.10` when published `<= 30d` ago; linear decay to `0.0` at `>= 180d`; `0.0` if publication date unknown |
| `corroboration_bonus` | `+0.05` per corroborating claim, capped at `+0.15` (saturates at 3) |
| `anecdotal_penalty` | flat `-0.10` on `personal_anecdote` and `unclassified` |
| `contradiction_penalty` | `-0.15` per contradicting claim, capped at `-0.45` (saturates at 3) |
| `stale_penalty` | `0.0` until 30d before expiry; linear ramp to `-0.15` at expiry; further to `-0.30` capped past expiry |

Recency and corroboration caps are deliberately small so they act as
tiebreakers, not bucket-movers: a fresh, triply-corroborated `personal_anecdote`
still ceilings at `low`. Contradiction is the strongest negative signal so a
couple of credible contradictions can drop a fresh `company_engineering_blog`
from `high` to `medium`. The `stale_penalty` (a smooth ranking signal) is
distinct from the hard expiry boolean (a claim past `expires_at` is ineligible
to drive generation, enforced in syllabus validation).

### Base score and expiration additions

- `canonical_topic_module` — omitted from the axiom tables above but named in the
  expiration table. Scored as curated high-trust internal content: base **0.85**,
  expiry **730 days** ("2+ years"). It is produced only by an internal curation
  path, never by URL classification.
- Single expiry-window values chosen inside each range (days):
  `official_job_posting` 45 (30–60), `interview_report` 120 (90–180),
  `role_taxonomy` 180, `company_engineering_blog` 540 (365–730). Windows the
  table leaves unspecified are set conservatively and flagged as priors:
  `interview_postmortem` 120 (reuses interview_report), `personal_anecdote` 90,
  `unclassified` 30 (shortest, provenance unknown).

Expiry is measured from `source_published_date` when present, else
`date_collected`. The boundary is inclusive (`expires_at <= now` is expired),
matching every other expiry in the system.

### Company context for classification (Phase 5)

"Company careers domain", "company engineering blog", and "personal blog" are
not decidable from a URL alone — the first two depend on which companies the
user targets, and any domain could be a personal blog. `classify_source` and
`SourceClaimIngestor` therefore accept optional `known_company_domains` /
`engineering_blog_hosts` (supplied by the composition root from `CompanyTarget`
objects — the same company context that feeds the cache's `company_target`,
axiom 18) and `personal_blog_hosts` (the only path to `personal_anecdote`).
Hosts are declared explicitly by the operator; without them, such hosts fall
through to `unclassified` rather than being guessed. In particular, no
platform host (Medium, Substack, etc.) is hardcoded as a personal blog, because
those same platforms also host official company engineering blogs.

## Related Docs

- `01-system-boundaries.md`
- `03-data-contracts.md`
- `18-caching-strategy.md`
- `../specs/source-claim.schema.md`
- `../decisions/ADR-0005-structured-syllabus-not-prose.md`
