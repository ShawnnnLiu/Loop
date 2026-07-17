# Placement Evidence Schema

## Owner

Scheduler placement scoring (`scheduler/scoring.py` evidence-affinity term;
axiom 05 "Evidence-affinity term"). Composed by the app layer
(`app/cycle.py`), consumed by the Scheduler through `SchedulerInput`.

## Consumers

Scheduler placement loop, schedule-quality reporting, engineering review.

## Purpose

The scheduler stays a pure function of `SchedulerInput`; per-user
time-of-day evidence — where the user historically works best — reaches
placement only through this contract. `PlacementEvidence` is a list of
`EvidenceCell` statements keyed by `(category, time_of_day_band)`: "for
PRACTICE tasks in the evening band, this user's observed duration
multiplier is 0.85." The placement scorer converts that into a bonus (or
penalty) on candidate starts inside the band; evidence **biases where a
task goes, never how long it is** — `estimated_duration_min` stays whatever
the Planner + calibration pipeline produced (axiom 17). All derivation is
deterministic counting and weighted medians/averages — no ML (ADR-0004).

## Shape

`PlacementEvidence` = `{ cells: EvidenceCell[] }` (empty by default —
no evidence means placement scoring runs exactly as before).

`EvidenceCell`:

| Field | Type | Rules |
| --- | --- | --- |
| `category` | `TaskCategory` | task-plan category vocabulary (`contracts/common_types.py`) |
| `time_of_day_band` | `TimeOfDayBand` | the pooled-duration band vocabulary (`contracts/pooled_duration_model.py`) — one band definition in the codebase, ever |
| `multiplier` | `float \| null` | bounded `[0.5, 2.0]` (the calibration clamp band); REQUIRED for `pooled` / `per_user_refined` cells, FORBIDDEN for `revealed` cells |
| `weighted_sample` | `float` | > 0; the evidence mass behind the cell (for `revealed` cells: the observation count) |
| `source` | enum | `pooled` \| `per_user_refined` \| `revealed` |

Uniqueness invariant: no two cells share `(category, time_of_day_band,
source)`. The key deliberately includes `source` — a `(category, band)`
pair may legitimately carry both a `pooled` and a `per_user_refined` cell;
consumers resolve precedence, not the contract.

## Composition Rules (app layer)

- **Pooled cells** are consent-gated (ADR-0007): the composition root
  checks `pooled_serving` consent exactly like pooled duration serving and
  emits zero pooled cells on denial. The gate is consulted only when a
  pooled artifact is actually offered, so the no-artifact path writes no
  audit rows.
- Pooled cells condition on the user's `experience_level` and marginalize
  the remaining non-`(category, band)` bucket features (`cognitive_load`,
  `day_of_week`, `completion_rate_band`, `multiplier_band`): matching
  buckets aggregate by `weighted_sample`-weighted average (single match
  uses the bucket value directly — no float drift), mirroring the pooled
  serving path.
- **Serving-floor discipline**: a cell whose combined `weighted_sample` is
  below `pooled_serving.serving_floor` is not emitted — for pooled and
  refined cells alike.
- **Refined cells** map `PerUserRefinement` entries 1:1; the refinement
  tier is the user's own data and is not consent-gated (mirroring
  `resolve_duration_multiplier`).
- **Revealed cells** aggregate `PlacementPreferenceObservation` rows
  (`placement-preference.schema.md`): observations within the last
  `revealed_window_days` days, grouped by `(category, band)`, emit one
  `revealed` cell when the group's count reaches
  `revealed_min_observations` — `weighted_sample = float(count)`, no
  multiplier. The user's own behavior: not consent-gated, and governed by
  its own count threshold, not the pooled `serving_floor`.
- Multipliers are clamped into `[0.5, 2.0]` at composition; the contract
  enforces the same bounds.
- Cells are emitted in canonical `(category, time_of_day_band, source)`
  sort order.

Production reality: no pooled-artifact store exists in the solo MVP and
the power-user refinement tier has no runtime producer, so those two
tiers are dormant — nothing user-facing may describe pooled-evidence
placement as live until an artifact actually flows in production. The
**revealed tier is the live tier**: its observations are produced by the
user's own drag-adjust and reconciliation-adoption actions, which exist
in the solo MVP today.

## Scoring Semantics (scheduler)

Exact integer form (axiom 05 "Evidence-affinity term"):

- `mult_pct = round(multiplier × 100)` — an int in `[50, 200]`; the one
  float-to-int conversion, done once per run.
- A candidate whose `(task.category, band(candidate_start))` matches a
  cell contributes `w_evidence_affinity × (mult_pct − 100) × duration
  // 100` to its cost — negative (a bonus) when the user is historically
  faster in that band (`multiplier < 1`), positive when slower.
- If both a `pooled` and a `per_user_refined` cell match the same
  `(category, band)`, `per_user_refined` wins — the more specific tier.
- Missing cell — or empty evidence — contributes exactly 0: schedules are
  byte-identical to evidence-free runs.

Revealed cells score separately (axiom 05 "Revealed-preference term") —
they carry no multiplier, so the percent form cannot apply. A candidate
whose `(task.category, band(candidate_start))` matches a `revealed` cell
gets a flat bonus: `cost -= w_revealed_affinity × duration`. The term is
independent of — and stacks with — the multiplier term when both a
multiplier-bearing cell and a revealed cell match the same key.

## JSON Example

```json
{
  "cells": [
    {
      "category": "concept_review",
      "time_of_day_band": "morning",
      "multiplier": 1.2,
      "weighted_sample": 7.5,
      "source": "pooled"
    },
    {
      "category": "practice",
      "time_of_day_band": "evening",
      "multiplier": 0.85,
      "weighted_sample": 12.0,
      "source": "pooled"
    },
    {
      "category": "practice",
      "time_of_day_band": "evening",
      "multiplier": 0.8,
      "weighted_sample": 6.0,
      "source": "per_user_refined"
    },
    {
      "category": "practice",
      "time_of_day_band": "evening",
      "multiplier": null,
      "weighted_sample": 3.0,
      "source": "revealed"
    }
  ]
}
```

## Validation Rules

- `category` and `time_of_day_band` must be members of their shared
  vocabularies.
- `multiplier`, when present, must lie in `[0.5, 2.0]`.
- `multiplier` is required for `pooled` and `per_user_refined` cells and
  forbidden for `revealed` cells.
- `weighted_sample` > 0.
- `(category, time_of_day_band, source)` triples are unique.

## Invalid Examples

```json
{ "cells": [ { "category": "practice", "time_of_day_band": "midnight", "...": "..." } ] }
```

Reason: unknown time-of-day band.

```json
{ "cells": [ { "category": "practice", "time_of_day_band": "evening", "multiplier": null, "weighted_sample": 12.0, "source": "pooled" } ] }
```

Reason: a pooled cell requires a multiplier.

```json
{ "cells": [ { "category": "practice", "time_of_day_band": "evening", "multiplier": 0.9, "weighted_sample": 3.0, "source": "revealed" } ] }
```

Reason: a revealed cell must not carry a multiplier — it states a location
preference, never a duration claim.

```json
{ "cells": [ { "multiplier": 2.5, "...": "..." } ] }
```

Reason: multiplier outside the `[0.5, 2.0]` calibration band.

```json
{ "cells": [ { "category": "practice", "time_of_day_band": "evening", "source": "pooled", "...": "..." }, { "category": "practice", "time_of_day_band": "evening", "source": "pooled", "...": "..." } ] }
```

Reason: duplicate `(category, time_of_day_band, source)` cell.

## Related Docs

- `placement-preference.schema.md`
- `pooled-duration-model.schema.md`
- `power-user-eligibility.schema.md`
- `consent-record.schema.md`
- `../axioms/05-scheduler-policy.md`
- `../axioms/17-duration-estimation.md`
- `../decisions/ADR-0004-no-per-user-ml-model-in-mvp.md`
- `../decisions/ADR-0007-consent-gated-deterministic-pooled-personalization.md`
- `../implementation-plans/scheduler-placement-quality/03-evidence-driven-placement.md`
