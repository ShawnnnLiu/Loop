# Pooled Duration Model Schema

## Owner

Pooled-duration training (`duration_estimation/pooled.py`; ADR-0007).

## Consumers

Duration-estimation serving fallback chain, replan path
(`duration_estimation/transform.py`), metrics, engineering review.

## Purpose

A `PooledDurationModel` is the versioned, deterministic artifact produced by
pooled-duration training (axiom 17 Phase 3). It is **not an ML model**: every
value is pure arithmetic over explicit features — feature-bucketed pooled
multipliers with sample-size shrinkage toward a global prior — and rebuilding
from the same inputs yields a byte-identical artifact with the same
`content_hash` (replay determinism).

Only consented users' telemetry enters training (`pooled_training` consent
scope, ADR-0007). The artifact itself contains **no user identifiers** —
only feature buckets and aggregate statistics — so serving it leaks nothing
about any individual.

Pooled output feeds the deterministic Scheduler via the existing calibration
transform; it never replaces it, and its absence, sparsity, or invalidity
never blocks planning (fallback chain below).

## Feature Dimensions

Training buckets are keyed by the explicit feature tuple from the Phase 6
plan. In this codebase `TaskCategory` carries the axiom-17 task-type values
(`concept_review`, `practice`, `mock_interview`, `project`, …), and the
`Task` contract has no separate type field — so "task category" and "task
type" fold into the single `category` dimension (the same collapsing the
drift-event spec applies to category granularity).

| Field | Values | Derivation |
| --- | --- | --- |
| `category` | `TaskCategory` enum | `Task.category` via the caller's `task_id → category` map. |
| `cognitive_load` | integer 1–5 | `Task.cognitive_load`. |
| `experience_level` | `beginner`, `intermediate`, `advanced` | `UserProfile.experience_level`, supplied by the caller. |
| `time_of_day_band` | `morning` (05:00–11:59), `afternoon` (12:00–16:59), `evening` (17:00–21:59), `night` (22:00–04:59) | Hour of `completion_timestamp` in the user's IANA timezone (caller-supplied). |
| `day_of_week` | `mon` … `sun` | Same localized timestamp. |
| `completion_rate_band` | `low` (< 0.5), `medium` (0.5 ≤ r < 0.8), `high` (≥ 0.8) | Caller-supplied recent completion rate in `[0, 1]`. |
| `multiplier_band` | `faster` (m < 0.9), `baseline` (0.9 ≤ m ≤ 1.1), `slower` (m > 1.1) | The user's existing per-category multiplier (Phase 2 calibration); 1.0 when absent. |

Band boundaries are uncalibrated heuristic priors (axiom 07 threshold
honesty).

## Training Rules

- **Consent filter first.** Events from users outside the caller-supplied
  consented set never enter any statistic — not the buckets and not the
  global prior. (The composition root audits the consent checks through the
  consent gate; the trainer enforces the filter again on its inputs.)
- **Event eligibility** mirrors Phase 2 calibration
  (`telemetry/calibration.py`): completed events with a real measured
  `actual_duration_min` (`duration_estimated` events excluded), weighted by
  data quality (`complete`/`offline_synced` 1.0; `partial_estimated`/
  `manual_backfill` 0.5).
- **Global prior**: the weighted median of all eligible consented ratios
  (`actual / scheduled`), clamped to the multiplier band; its weighted sample
  is recorded. With no eligible events the prior is 1.0 with sample 0.
- **Shrinkage**: each bucket's raw statistic is the weighted median of its
  ratios; the published multiplier blends it toward the global prior by
  sample size:

  ```text
  multiplier = clamp(
      (weighted_sample * bucket_median + shrinkage_strength * global_prior)
      / (weighted_sample + shrinkage_strength),
      multiplier_min, multiplier_max)
  ```

  `shrinkage_strength` (default 5.0) and the clamp band (default
  [0.5, 2.0], matching Phase 2 calibration) are heuristic priors and are
  recorded on the artifact for audit/replay.
- **Determinism**: buckets are emitted in canonical feature order; the same
  inputs produce a byte-identical artifact and `content_hash`. Training is a
  pure function — the caller supplies `trained_at` and `model_version`.

## Serving And Fallback Chain

Serving resolves one effective multiplier per task category through a
deterministic chain. Each skipped tier records a typed `reason_code`; the
result names the source that won, so every estimate is explainable.

1. **Pooled** — query the artifact with the known serving features
   (`category`, `experience_level`, `completion_rate_band`,
   `multiplier_band`). At replan time the scheduled slot and per-task load
   are not yet known, so serving marginalizes over `cognitive_load`,
   `time_of_day_band`, and `day_of_week`: all matching buckets combine by
   `weighted_sample`-weighted mean, clamped to the artifact's clamp band.
   The pooled tier is used only when the combined `weighted_sample` meets
   `serving_floor` (default 5.0, heuristic prior). Skip reasons:
   - `CONSENT_MISSING` / `CONSENT_REVOKED` — the consent gate denied
     `pooled_serving` (the caller passes the gate decision in).
   - `POOLED_MODEL_UNAVAILABLE` — no artifact, or the artifact failed
     contract validation (e.g. `content_hash` mismatch).
   - `POOLED_BUCKET_SPARSE` — no matching bucket, or combined weighted
     sample below `serving_floor`.
2. **Per-user category multiplier** — the Phase 2 calibration value
   (`UserDurationMultipliers`), when present for the category.
3. **Heuristic baseline** — multiplier 1.0: the task keeps its axiom 17
   Phase 1 heuristic estimate unchanged.

Pooled failure therefore **never blocks planning**: the chain always
produces a multiplier. Plan application feeds the resolved per-category
multipliers through `duration_estimation/transform.apply_duration_calibration`,
producing a new draft plan version via the replan path — the active plan is
never mutated.

## JSON Example

```json
{
  "model_version": "pooled-2026-06-10",
  "feature_schema_version": "1",
  "trained_at": "2026-06-10T09:00:00-07:00",
  "global_prior_multiplier": 1.12,
  "global_prior_weighted_sample": 42.0,
  "shrinkage_strength": 5.0,
  "multiplier_min": 0.5,
  "multiplier_max": 2.0,
  "buckets": [
    {
      "category": "practice",
      "cognitive_load": 4,
      "experience_level": "beginner",
      "time_of_day_band": "evening",
      "day_of_week": "tue",
      "completion_rate_band": "medium",
      "multiplier_band": "slower",
      "multiplier": 1.31,
      "sample_size": 6,
      "weighted_sample": 5.5,
      "observed_ratio": 1.4
    }
  ],
  "content_hash": "sha256:..."
}
```

## Field Definitions

| Field | Type | Purpose |
| --- | --- | --- |
| `model_version` | string | Operator-facing label for this build. Not hashed — two builds of the same data under different labels share a `content_hash`. |
| `feature_schema_version` | string | Version of the feature-tuple definition above; a feature change bumps it and forces regeneration. |
| `trained_at` | datetime | When the artifact was built (caller's clock). Not hashed. |
| `global_prior_multiplier` | float > 0 | Clamped weighted median over all consented eligible ratios. |
| `global_prior_weighted_sample` | float ≥ 0 | Weighted evidence behind the prior. |
| `shrinkage_strength` | float ≥ 0 | The `k` in the shrinkage blend; recorded for audit/replay. |
| `multiplier_min` / `multiplier_max` | float > 0 | Clamp band applied at training and serving; `max` ≥ `min`. |
| `buckets[*]` | object | One entry per observed feature tuple: the seven feature fields, the shrunk `multiplier`, raw `sample_size` (event count ≥ 1), `weighted_sample` (> 0), and the pre-shrinkage `observed_ratio` for audit. |
| `content_hash` | string `sha256:<64-hex>` | `canonical_mapping_hash` over the hashed payload (everything above except `model_version` and `trained_at`). Recomputed by the contract validator; a mismatch rejects the artifact. |

## Invariants

- Bucket feature tuples are unique, and buckets are stored in canonical
  sorted order (the trainer's emission order; validated so the hash is
  well-defined).
- `content_hash` must equal the recomputed hash of the artifact's hashed
  payload — a tampered or corrupted artifact fails validation and the
  serving chain treats it as `POOLED_MODEL_UNAVAILABLE`.
- Every bucket multiplier and the global prior lie within
  `[multiplier_min, multiplier_max]`.
- `trained_at` must be timezone-aware.
- The artifact contains no user identifiers and no free text.
- LLMs play no role anywhere in this pipeline.

## Invalid Examples

```json
{ "content_hash": "sha256:0000000000000000000000000000000000000000000000000000000000000000" }
```

Reason: hash does not match the recomputed canonical hash (tampered/corrupt).

```json
{ "buckets": [ { "...": "same feature tuple twice" } ] }
```

Reason: duplicate bucket feature tuples.

```json
{ "global_prior_multiplier": 2.5, "multiplier_max": 2.0 }
```

Reason: prior outside the artifact's own clamp band.

## Related Docs

- `consent-record.schema.md`
- `data-access-audit.schema.md`
- `telemetry.schema.md`
- `../axioms/17-duration-estimation.md`
- `../axioms/07-telemetry-and-drift.md`
- `../decisions/ADR-0007-consent-gated-deterministic-pooled-personalization.md`
