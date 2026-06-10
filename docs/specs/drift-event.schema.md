# Drift Event Schema

## Owner

Deterministic drift classifier.

## Consumers

Supervisor, replan flow, metrics, `UserFacingExplanationNode`.

## Purpose

Capture the deterministic classification that the current plan no longer matches the user's execution reality. The MVP classifier is rule-based; the LLM may explain the result but must not classify drift.

## JSON Example

```json
{
  "drift_event_id": "drift_001",
  "plan_version": "plan_v3",
  "drift_detected": true,
  "drift_type": "duration_underestimate",
  "reason_code": "DRIFT_DURATION_UNDERESTIMATE",
  "confidence": 0.82,
  "evidence": {
    "trigger_metric": "median_actual_vs_predicted_ratio",
    "trigger_value": 1.48,
    "threshold": 1.3,
    "sample_size": 6,
    "affected_categories": ["practice"]
  },
  "recommended_policy_action": "increase_duration_estimates_for_category",
  "detected_at": "2026-05-12T08:00:00-07:00"
}
```

## Field Semantics

| Field | Purpose |
| --- | --- |
| `drift_event_id` | Unique id for this classification; the audit/store key |
| `plan_version` | The active plan version the drift was computed against; a replan derives the next version from it |
| `drift_detected` | Boolean flag |
| `drift_type` | One of the allowed drift types |
| `reason_code` | Typed `ReasonCode` (the `DRIFT_*` family) mirroring `drift_type`; carries drift into the system-wide typed-failure vocabulary |
| `confidence` | Deterministic numeric score in `[0, 1]` |
| `evidence` | Structured evidence supporting the classification (see "Evidence Shape") |
| `recommended_policy_action` | Deterministic next action selected by the policy engine |
| `detected_at` | Timezone-aware timestamp of classification |

## Evidence Shape

Evidence is uniform across drift types so every event self-documents *which
metric crossed which threshold over how many samples*. This keeps the payload
validateable and the classifier output auditable.

| Field | Required | Purpose |
| --- | --- | --- |
| `trigger_metric` | yes | Name of the metric that fired (e.g. `median_actual_vs_predicted_ratio`, `weekly_completion_ratio`, `reschedule_count`, `largest_free_block_min`) |
| `trigger_value` | yes | The observed value of `trigger_metric` |
| `threshold` | yes | The threshold value the metric crossed |
| `sample_size` | yes | Number of telemetry events / cycles the decision rests on (`>= 0`) |
| `affected_categories` | no | `TaskCategory` values the drift is scoped to (empty for global drift) |

**Category granularity.** In the MVP, `affected_categories` holds
`TaskCategory` values (the structured field on `Task`). Finer topic-level
multipliers (e.g. `dynamic_programming`, `arrays` per axiom 17) are deferred
until tasks carry a topic dimension; Phase 4 calibrates at `TaskCategory`
granularity.

## Allowed `drift_type` Values

- `capacity_mismatch`
- `duration_underestimate`
- `duration_overestimate`
- `topic_avoidance`
- `external_conflict`
- `low_engagement`
- `dependency_blocked`
- `calendar_fragmentation`
- `accountability_mismatch` (Phase 7)
- `sponsor_pressure_mismatch` (Phase 7)

See `../axioms/07-telemetry-and-drift.md` for triggers and recommended responses.

## Accountability-Coupled Drift Types (Phase 7)

The two accountability-coupled types from the axiom 07 table land with the
Phase 7 accountability layer. They classify from **observable behavior only**
— the classifier still never reads the motivation profile
(`motivation-profile.schema.md` consumer note); the caller derives the counts
from stores:

| Type | Trigger (deterministic, heuristic priors) | Evidence `trigger_metric` |
| --- | --- | --- |
| `accountability_mismatch` | Missed events ≥ `accountability_min_missed` (3) AND explicitly declined/ignored accountability interventions ≥ `accountability_min_declined` (1) in the window (caller-derived `declined_interventions`: revoked sponsors, unanswered recommitment requests) | `declined_interventions_with_repeated_misses` |
| `sponsor_pressure_mismatch` | Sponsor reporting observably disabled in the window after ≥ `sponsor_pressure_min_reports` (2) reports were sent (caller-derived `sponsor_reports_sent_recent`, `sponsor_reporting_disabled`) | `sponsor_reports_before_disable` |

The classifier identifies the mismatch; the Accountability Policy Engine
(axiom 21), never the LLM, decides the response. Neither type ever produces a
sponsor notification (golden scenario 23).

## Allowed `reason_code` Values

`reason_code` is a member of the system-wide `ReasonCode` enum, mapping 1:1 to
`drift_type`. The eight Phase 4 types use the `DRIFT_*` family; the two
accountability-coupled types use the accountability-family names —
`ACCOUNTABILITY_MISMATCH` is the canonical code from axiom 16's accountability
set, and `SPONSOR_PRESSURE_MISMATCH` mirrors it (defined by this spec, per
axiom 16's "other reason codes are defined in specs" note):

- `DRIFT_CAPACITY_MISMATCH`
- `DRIFT_DURATION_UNDERESTIMATE`
- `DRIFT_DURATION_OVERESTIMATE`
- `DRIFT_TOPIC_AVOIDANCE`
- `DRIFT_EXTERNAL_CONFLICT`
- `DRIFT_LOW_ENGAGEMENT`
- `DRIFT_DEPENDENCY_BLOCKED`
- `DRIFT_CALENDAR_FRAGMENTATION`
- `ACCOUNTABILITY_MISMATCH`
- `SPONSOR_PRESSURE_MISMATCH`

## Invariants

- Drift classification is deterministic in the MVP.
- `drift_type` must be one of the allowed values.
- `reason_code` must be the code that corresponds 1:1 to `drift_type`.
- Every event must include `evidence` with `sample_size` and the `trigger_metric`/`trigger_value`/`threshold` that triggered classification.
- A `DriftEvent` always represents a *detected* drift: `drift_detected` is `true`, and `drift_type`, `reason_code`, `evidence`, and `recommended_policy_action` are all present. The absence of drift is an empty classifier result (no events), never a `drift_detected: false` record. This keeps the classifier's `list[DriftEvent]` contract unambiguous and drives the Supervisor `DRIFT_DETECTED` vs `NO_DRIFT` signal off list non-emptiness.
- Drift events may recommend replanning but cannot approve calendar changes.
- `confidence` must be a numeric value in `[0, 1]`, never an LLM-generated string.
- `detected_at` must be timezone-aware.

## Recommended Policy Actions

Examples of allowed `recommended_policy_action` values:

- `reduce_weekly_load`
- `extend_timeline`
- `increase_duration_estimates_for_category`
- `decrease_duration_estimates_for_category`
- `add_review_block`
- `split_topic_into_smaller_tasks`
- `reschedule_around_conflict`
- `reschedule_prerequisite_first`
- `ask_user_to_adjust_goal`
- `revise_accountability_contract` (Phase 7: `accountability_mismatch`)
- `switch_to_private_recovery` (Phase 7: `sponsor_pressure_mismatch` — reduce external reporting, recover privately)

## Invalid Examples

```json
{ "drift_type": "bad_vibes", "confidence": "high" }
```

Reason: invalid drift type and non-numeric confidence.

```json
{ "drift_type": "capacity_mismatch", "evidence": {} }
```

Reason: missing evidence and trigger metric.

```json
{
  "drift_detected": true,
  "drift_type": "duration_underestimate",
  "confidence": 1.5
}
```

Reason: confidence out of range.

## Related Docs

- `../axioms/07-telemetry-and-drift.md`
- `../axioms/12-edge-case-policy-engine.md`
- `../axioms/17-duration-estimation.md`
- `telemetry.schema.md`
- `../axioms/02-state-machine.md`
