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
  "drift_detected": true,
  "drift_type": "duration_underestimate",
  "confidence": 0.82,
  "evidence": {
    "median_actual_vs_predicted_ratio": 1.48,
    "affected_categories": ["dynamic_programming"],
    "sample_size": 6
  },
  "recommended_policy_action": "increase_duration_estimates_for_category"
}
```

## Field Semantics

| Field | Purpose |
| --- | --- |
| `drift_detected` | Boolean flag |
| `drift_type` | One of the allowed drift types |
| `confidence` | Deterministic numeric score in `[0, 1]` |
| `evidence` | Structured evidence supporting the classification |
| `recommended_policy_action` | Deterministic next action selected by the policy engine |

## Allowed `drift_type` Values

- `capacity_mismatch`
- `duration_underestimate`
- `duration_overestimate`
- `topic_avoidance`
- `external_conflict`
- `low_engagement`
- `dependency_blocked`
- `calendar_fragmentation`

See `../axioms/07-telemetry-and-drift.md` for triggers and recommended responses.

## Invariants

- Drift classification is deterministic in the MVP.
- `drift_type` must be one of the allowed values.
- Every event must include `evidence` with sample size and the metric that triggered classification.
- Drift events may recommend replanning but cannot approve calendar changes.
- `confidence` must be a numeric value, never an LLM-generated string.

## Recommended Policy Actions

Examples of allowed `recommended_policy_action` values:

- `reduce_weekly_load`
- `extend_timeline`
- `increase_duration_estimates_for_category`
- `decrease_duration_estimates_for_category`
- `add_review_block`
- `split_topic_into_smaller_tasks`
- `reschedule_around_conflict`
- `ask_user_to_adjust_goal`

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
