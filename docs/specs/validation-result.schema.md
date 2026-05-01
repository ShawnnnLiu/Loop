# Validation Result Schema

## Owner

Deterministic validation layer.

## Consumers

Supervisor, repair loop, Scheduler gate, user-facing explanations.

## Purpose

A typed result object that captures whether an artifact passed validation, the typed reason for failure, the structured violations, and the next deterministic action.

## JSON Example (Failure)

```json
{
  "run_id": "run_2026_05_04_001",
  "artifact_type": "task_plan",
  "valid": false,
  "repairable": true,
  "reason_code": "TASK_GRAPH_INVALID",
  "violations": [
    {
      "type": "orphan_dependency",
      "task_id": "dp_004",
      "invalid_dependency": "dp_999"
    },
    {
      "type": "module_coverage_missing",
      "module_id": "api_design"
    },
    {
      "type": "duration_exceeds_user_max_session",
      "task_id": "system_design_003",
      "duration_min": 180,
      "max_session_length_min": 120
    }
  ],
  "repair_attempt": 1,
  "max_repair_attempts": 2,
  "next_action": "planner_repair_retry"
}
```

## JSON Example (Success)

```json
{
  "run_id": "run_2026_05_04_001",
  "artifact_type": "task_plan",
  "valid": true,
  "repairable": false,
  "reason_code": null,
  "violations": [],
  "repair_attempt": 0,
  "max_repair_attempts": 2,
  "next_action": "scheduler"
}
```

## Field Semantics

| Field | Purpose |
| --- | --- |
| `run_id` | Correlates the result with the request that produced it |
| `artifact_type` | The kind of artifact validated, e.g. `task_plan`, `syllabus_units` |
| `valid` | Boolean pass/fail |
| `repairable` | Whether the failure is eligible for an LLM repair attempt |
| `reason_code` | Typed reason code; required when `valid` is false |
| `violations` | Structured list of failed checks, each with a `type` and supporting fields |
| `repair_attempt` | The current repair attempt number, starting at 0 |
| `max_repair_attempts` | Hard cap of 2 for LLM-generated artifacts |
| `next_action` | Deterministic next step, e.g. `planner_repair_retry`, `scheduler`, `error_requires_user` |

## Violation Types

Recommended `type` values include:

- `orphan_dependency`
- `cycle_detected`
- `self_dependency`
- `duplicate_task_id`
- `missing_module_id`
- `module_coverage_missing`
- `duration_exceeds_user_max_session`
- `cognitive_load_out_of_range`
- `category_invalid`
- `focus_level_invalid`
- `weekly_load_exceeds_capacity`

Each violation must carry the structured fields required to repair it.

## Invariants

- Invalid results must include a typed `reason_code`.
- `violations` must be non-empty when `valid` is false.
- `max_repair_attempts` is `2` for LLM-generated artifacts.
- Scheduler only accepts results where `valid` is true for required inputs.
- Validation must not mutate the artifact under test.
- A successful result must carry an empty `violations` list.

## Invalid Examples

```json
{ "valid": false, "violations": [] }
```

Reason: failure with no typed reason or evidence.

```json
{ "valid": true, "violations": [{ "type": "cycle_detected" }] }
```

Reason: success cannot carry violations.

```json
{ "valid": false, "reason_code": "TASK_GRAPH_INVALID", "repair_attempt": 5 }
```

Reason: exceeds `max_repair_attempts`.

## Related Docs

- `../axioms/04-validation-layer.md`
- `../axioms/16-reliability-patterns.md`
- `task-plan.schema.md`
- `scheduler-output.schema.md`
