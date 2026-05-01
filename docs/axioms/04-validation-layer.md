# 04: Validation Layer

## Purpose

The Validation Layer is a deterministic gate between Planner and Scheduler. It prevents invalid LLM output from reaching the calendar scheduling layer.

Invalid Planner output must never reach the Scheduler.

## Validation Categories

The validator checks:

1. **Schema validity** — required fields, enum values, timestamps, numeric ranges, object shapes.
2. **Graph integrity** — dependency structure, duplicates, cycles.
3. **Syllabus coverage** — every required module is represented.
4. **User fit** — plan matches profile capacity and preferences.
5. **Workload sanity** — total load within capacity tolerances.
6. **Scheduling preconditions** — tasks are schedulable before invoking Scheduler.

## Schema Checks

- Required fields exist.
- Field types are valid.
- Enums are valid.
- Duration is within bounds.
- Cognitive load is between 1 and 5.
- Every task has a `module_id`.
- Every task has a stable `task_id`.
- Every dependency list is an array.
- `splittable` is boolean.

## Graph Checks

- No duplicate task IDs.
- No orphan dependencies.
- No cycles.
- No self-dependencies.
- Topological sort succeeds.
- Every dependency references an existing task.

## Syllabus Coverage Checks

- Every high-priority module has at least one task.
- Every task references a valid `module_id`.
- Total task time per module is within tolerance of module estimate.
- No low-priority module consumes disproportionate time.
- No required module is silently dropped.

## User-Fit Checks

- Total weekly estimated load <= user weekly availability * 1.2.
- No task exceeds `max_session_length_min` unless `splittable` is true.
- Beginner users are not overloaded with high-load tasks early.
- High-cognitive-load tasks are distributed across the plan.
- Tasks roughly match `preferred_session_length_min` when possible.

## Repair Policy

The validator supports a bounded repair loop:

1. Validation failure produces structured violations.
2. Violations are sent to the Planner for one repair attempt.
3. If a second failure occurs, route to user approval / error gate.
4. Hard cap: **2 repair attempts** per artifact.

The repair loop must not let the LLM override the failed checks. It must only send the original candidate and the structured violations.

## Structured Repair Payload

```json
{
  "repair_reason": "validation_failed",
  "artifact_type": "task_plan",
  "attempt": 1,
  "max_attempts": 2,
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
  ]
}
```

## Validation Output

```json
{
  "valid": false,
  "repairable": true,
  "violations": [],
  "next_action": "planner_repair_retry"
}
```

After two failed repairs, the Supervisor emits `error_requires_user` with a typed `reason_code`.

## Validation Failure Transparency

### The Silent Regeneration Problem

When the validator rejects Planner output and triggers a repair retry, the user typically sees a loading spinner with no explanation. If the repair also fails, the user sees an approval gate with no context. This erodes trust because the user cannot tell whether the system is broken, slow, or working as designed.

### Cycle-Level Debug Surface

Every validation failure must produce a user-readable explanation, even when the system auto-repairs successfully. Surface this in two places:

- **During regeneration (passive).** A status line under the loading indicator: "Adjusting plan — initial draft had a task longer than your max session length. Generating a revised version."
- **Plan history (persistent).** Every plan version records its generation history, including failed validation attempts and the violations that caused them. The approval UI must include an expandable "How was this plan made?" section showing each attempt and what changed.

### User-Facing Violation Translation

Validation `reason_code` and violation `type` values are engineer-facing. Each must have a corresponding user-facing translation. The translation table is stored deterministically; the LLM must not invent translations on the fly.

| Violation Type | User-Facing Explanation |
| --- | --- |
| `orphan_dependency` | "A task referenced a prerequisite that doesn't exist. Fixing now." |
| `cycle_detected` | "Two tasks depend on each other in a loop. Restructuring." |
| `duration_exceeds_user_max_session` | "A task was too long for your session preferences. Splitting it up." |
| `module_coverage_missing` | "An important module was missing tasks. Adding them." |
| `weekly_load_exceeded` | "The plan exceeded your weekly hours. Trimming scope." |
| `cognitive_load_out_of_range` | "A task's difficulty rating was invalid. Recalibrating." |
| `category_invalid` | "A task type was unrecognized. Replacing with a valid type." |
| `focus_level_invalid` | "A task's focus level was unrecognized. Replacing with a valid level." |
| `self_dependency` | "A task depended on itself. Removing the cycle." |
| `duplicate_task_id` | "Two tasks shared the same ID. Re-numbering." |

The `UserFacingExplanationNode` may compose multi-violation summaries from these strings, but the source phrases come from this deterministic table.

### Mandatory User Action After Repair Limit

After **2 failed repair attempts** (the existing hard cap), the system MUST:

1. Halt automatic regeneration.
2. Surface a user action card with:
   - Plain-language summary of why generation failed.
   - The specific violation(s) blocking progress.
   - 2–4 multiple-choice remediation options (for example, "Reduce scope," "Extend timeline," "Loosen session length limit," "Edit profile manually").
   - A free-text override option.
3. Block all further auto-generation on this plan until user input is received.
4. Log the failure with full context (`run_id`, `plan_version`, attempt count, all violations) for engineering review.

This rule prevents the system from entering silent infinite loops or showing the user a generic error, both of which are trust-breaking.

### Plan Generation History

Each plan version stores a `generation_history` field consumed by the approval UI:

```json
{
  "plan_version": "plan_004",
  "generation_history": [
    {
      "attempt": 0,
      "outcome": "validation_failed",
      "reason_code": "TASK_GRAPH_INVALID",
      "violations_summary": [
        "1 task too long for your session preference",
        "1 module had no tasks"
      ]
    },
    {
      "attempt": 1,
      "outcome": "validation_passed",
      "reason_code": null
    }
  ]
}
```

Generation history is append-only and immutable.

## Related Docs

- `02-state-machine.md`
- `03-data-contracts.md`
- `12-edge-case-policy-engine.md`
- `../specs/task-plan.schema.md`
- `../specs/validation-result.schema.md`
