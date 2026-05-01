# Task Plan Schema

## Owner

`PlannerNode`, with deterministic validation before Scheduler use.

## Consumers

Validation layer, Scheduler, approval UI, telemetry, Calendar Write Manager.

## Purpose

Convert structured syllabus modules into executable tasks. The Planner is schema-bound. It must consider the user profile, syllabus units, and duration policy.

## Planner Inputs

```json
{
  "user_profile": {
    "weekly_hours": 8,
    "timeline_weeks": 10,
    "experience_level": "intermediate",
    "known_weaknesses": ["dynamic programming"],
    "preferred_session_length_min": 60,
    "max_session_length_min": 120
  },
  "syllabus_units": [],
  "duration_policy": {
    "min_task_duration_min": 15,
    "max_task_duration_min": 120,
    "default_session_length_min": 60
  },
  "planner_constraints": {
    "must_reference_module_id": true,
    "max_cognitive_load": 5,
    "allowed_categories": [
      "concept_review",
      "practice",
      "mock_interview",
      "project",
      "reflection",
      "review"
    ],
    "allowed_focus_levels": ["light", "medium", "deep"]
  }
}
```

## JSON Example

```json
{
  "plan_version": "plan_004",
  "tasks": [
    {
      "task_id": "dp_001",
      "module_id": "dp",
      "title": "Review DP state definitions",
      "description": "Study how to define state, transition, base case, and answer extraction.",
      "dependencies": [],
      "estimated_duration_min": 60,
      "cognitive_load": 4,
      "category": "concept_review",
      "required_focus_level": "deep",
      "splittable": false
    },
    {
      "task_id": "dp_002",
      "module_id": "dp",
      "title": "Solve 3 one-dimensional DP problems",
      "description": "Practice climbing stairs, house robber, and min cost climbing stairs.",
      "dependencies": ["dp_001"],
      "estimated_duration_min": 90,
      "cognitive_load": 5,
      "category": "practice",
      "required_focus_level": "deep",
      "splittable": true
    }
  ]
}
```

## Field Semantics

| Field | Purpose |
| --- | --- |
| `plan_version` | Stable identifier for this plan revision |
| `tasks[].task_id` | Stable identifier referenced by Scheduler, telemetry, calendar mappings |
| `tasks[].module_id` | Reference to a valid syllabus module |
| `tasks[].title` | Display title |
| `tasks[].description` | Concrete instructions for execution |
| `tasks[].dependencies` | List of `task_id` values that must complete first |
| `tasks[].estimated_duration_min` | Positive integer in minutes |
| `tasks[].cognitive_load` | Integer in `1..5` |
| `tasks[].category` | One of the `allowed_categories` |
| `tasks[].required_focus_level` | One of the `allowed_focus_levels` |
| `tasks[].splittable` | Whether the task may be split across sessions |

## Planner Allowed Behavior

- Create tasks.
- Assign module IDs.
- Propose dependencies.
- Estimate duration.
- Assign cognitive load.
- Mark whether a task is splittable.

## Planner Forbidden Behavior

- Decide whether prerequisites are met (forbidden by `../axioms/11-prerequisite-logic.md`).
- Write to the calendar.
- Bypass validation.
- Activate a plan.
- Mutate user profile.
- Silently drop high-priority modules.

## Invariants

- `task_id` values are unique.
- Every `module_id` references a valid syllabus unit.
- `dependencies` references existing tasks.
- No self-dependencies.
- Task dependency graph has no cycles (topological sort succeeds).
- `estimated_duration_min` is a positive integer.
- Tasks where `estimated_duration_min > max_session_length_min` must have `splittable: true`.
- High-priority modules must have at least one task.
- `cognitive_load` is an integer in `[1, 5]`.
- `category` is in `allowed_categories`.
- `required_focus_level` is in `allowed_focus_levels`.
- `task_plan` must not include `prerequisites_met`. It is computed deterministically from `dependencies` and completion state.

## Invalid Examples

```json
{
  "tasks": [
    {
      "task_id": "dp_002",
      "module_id": "dp",
      "dependencies": ["dp_002"],
      "prerequisites_met": true
    }
  ]
}
```

Reason: self-dependency and forbidden `prerequisites_met`.

```json
{
  "tasks": [
    {
      "task_id": "a",
      "module_id": "missing",
      "estimated_duration_min": -1,
      "cognitive_load": 9
    }
  ]
}
```

Reason: orphan module, invalid duration, out-of-range cognitive load.

```json
{
  "tasks": [
    {
      "task_id": "long_task",
      "module_id": "dp",
      "estimated_duration_min": 180,
      "splittable": false,
      "category": "practice",
      "required_focus_level": "deep"
    }
  ]
}
```

Reason: exceeds `max_session_length_min` and not splittable (must trigger `TASK_TOO_LONG_UNSPLITTABLE`).

## Related Docs

- `../axioms/04-validation-layer.md`
- `../axioms/05-scheduler-policy.md`
- `../axioms/11-prerequisite-logic.md`
- `../axioms/15-plan-versioning-and-diffs.md`
- `validation-result.schema.md`
