# Power-User Eligibility Schema

## Owner

Power-user gate (`duration_estimation/power_user.py`; ADR-0007; axiom 17
Phase 4 thresholds).

## Consumers

Per-user refinement training, duration-estimation serving, metrics,
engineering review.

This spec defines two objects: `PowerUserEligibility` (the auditable gate
decision) and `PerUserRefinement` (the finer per-user multipliers trained
only behind the gate), mirroring how the sponsor-report spec covers its
companion objects.

## Purpose

Axiom 17 Phase 4 allows finer per-user modeling only for power users — a
per-user model trained on sparse data overfits. The gate is deterministic
and auditable like the accountability policy engine: every criterion is
evaluated (no short-circuit), every evaluation records the observed value
and threshold (`PolicyRuleEvaluation` pattern), and every **unmet** criterion
carries its own typed `reason_code`. The refinement that trains behind the
gate is still deterministic statistics — weighted medians per
(category × time-of-day band) — never ML (ADR-0004 stays in force).

## Eligibility Criteria

Eligibility is evaluated per `(user_id, category)`. All four criteria must
be met:

| Criterion | Met when | Unmet `reason_code` |
| --- | --- | --- |
| `total_completions` | total completed tasks ≥ 200 | `POWER_USER_TOTAL_COMPLETIONS_BELOW_THRESHOLD` |
| `category_completions` | completed tasks in the category ≥ 30 | `POWER_USER_CATEGORY_COMPLETIONS_BELOW_THRESHOLD` |
| `assessable_weeks` | assessable weeks ≥ 4 | `POWER_USER_INSUFFICIENT_ASSESSABLE_WEEKS` |
| `completion_rate_stability` | population variance of weekly completion rates over the assessable weeks ≤ the variance threshold (inclusive) | `POWER_USER_COMPLETION_RATE_UNSTABLE` |

Definitions:

- A week is **assessable** when its scheduled-task count ≥ 3 (a completion
  rate over fewer tasks is noise). Weekly aggregates
  (`scheduled_count`, `completed_count` per week) are supplied by the
  composition root, which knows the schedule; telemetry events alone cannot
  attribute scheduled-but-missed work to weeks.
- The weekly completion rate is `completed_count / scheduled_count` for an
  assessable week.
- The stability statistic is the **population variance** over assessable
  weeks' rates; with fewer than two assessable weeks it is defined as 0.0
  (the `assessable_weeks` criterion, not stability, reports the sufficiency
  problem — one observed value carries no instability evidence).
- The variance threshold (default 0.02) is clamped to `[0.0, 0.25]` at
  evaluation time. All thresholds here are uncalibrated heuristic priors
  (axiom 07): 200 / 30 / 4 weeks come from axiom 17 Phase 4.

Boundary semantics are pinned by tests: 199 fails / 200 passes, 29 fails /
30 passes, 3 weeks fail / 4 pass, variance exactly at the threshold passes.

## Refinement Rules

- `PerUserRefinement` trains **only** for `(user, category)` pairs whose
  eligibility object is `eligible: true`; ineligible categories produce no
  entries, so an ineligible user's serving behavior is byte-identical to
  Phase 6b.
- Entries are keyed by `(category, time_of_day_band)` — the same band
  derivation as the pooled model. Statistics mirror Phase 2 calibration:
  data-quality-weighted median of `actual / scheduled` ratios, a weighted
  sufficiency floor (default 5.0), and the [0.5, 2.0] clamp band.
- Serving uses a refined entry only when the caller knows the time-of-day
  band (e.g. rescheduling an already-placed task). The refined tier then
  outranks the pooled and per-user-category tiers (the most specific
  knowledge wins); when the band is unknown or no entry matches, the
  Phase 6b chain proceeds unchanged, recording
  `PER_USER_REFINEMENT_UNAVAILABLE` when a refinement was offered but
  unusable.

## JSON Example — `PowerUserEligibility`

```json
{
  "user_id": "user_123",
  "category": "practice",
  "evaluated_at": "2026-06-10T16:00:00Z",
  "eligible": false,
  "criteria": [
    {
      "criterion": "total_completions",
      "observed_value": 215.0,
      "threshold_value": 200.0,
      "met": true,
      "reason_code": null
    },
    {
      "criterion": "category_completions",
      "observed_value": 29.0,
      "threshold_value": 30.0,
      "met": false,
      "reason_code": "POWER_USER_CATEGORY_COMPLETIONS_BELOW_THRESHOLD"
    },
    {
      "criterion": "assessable_weeks",
      "observed_value": 6.0,
      "threshold_value": 4.0,
      "met": true,
      "reason_code": null
    },
    {
      "criterion": "completion_rate_stability",
      "observed_value": 0.011,
      "threshold_value": 0.02,
      "met": true,
      "reason_code": null
    }
  ]
}
```

## JSON Example — `PerUserRefinement`

```json
{
  "user_id": "user_123",
  "computed_at": "2026-06-10T16:00:00Z",
  "entries": [
    {
      "category": "practice",
      "time_of_day_band": "evening",
      "multiplier": 1.35,
      "sample_size": 14,
      "weighted_sample": 13.0,
      "observed_ratio": 1.35
    }
  ]
}
```

## Validation Rules

`PowerUserEligibility`:

- `evaluated_at` must be timezone-aware.
- `criteria` contains exactly the four criteria above, once each.
- `eligible` is true iff every criterion is `met`.
- An unmet criterion must carry exactly its criterion's reason code from the
  table; a met criterion must carry a null `reason_code`.

`PerUserRefinement`:

- `computed_at` must be timezone-aware.
- `(category, time_of_day_band)` pairs are unique.
- `multiplier`, `weighted_sample`, `observed_ratio` > 0; `sample_size` ≥ 1.

## Invalid Examples

```json
{ "eligible": true, "criteria": [ { "met": false, "...": "..." } ] }
```

Reason: eligible must equal the conjunction of the criteria.

```json
{ "criterion": "category_completions", "met": false, "reason_code": "POWER_USER_COMPLETION_RATE_UNSTABLE" }
```

Reason: an unmet criterion must carry its own reason code, not another's.

```json
{ "entries": [ { "category": "practice", "time_of_day_band": "evening" }, { "category": "practice", "time_of_day_band": "evening" } ] }
```

Reason: duplicate refinement key.

## Related Docs

- `pooled-duration-model.schema.md`
- `consent-record.schema.md`
- `../axioms/17-duration-estimation.md`
- `../axioms/12-edge-case-policy-engine.md`
- `../decisions/ADR-0007-consent-gated-deterministic-pooled-personalization.md`
