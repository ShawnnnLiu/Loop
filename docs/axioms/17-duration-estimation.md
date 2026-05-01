# 17: Task Time Estimation Strategy

## Principle

Duration estimates must start deterministic and become more sophisticated only after the deterministic core is proven and telemetry justifies the change.

## Phase 1: Heuristic Baseline (MVP)

The MVP uses deterministic heuristic estimates:

```text
estimated_duration =
  base_topic_duration
  * experience_multiplier
  * cognitive_load_multiplier
  * task_type_multiplier
  * user_category_multiplier
```

### Example Multipliers

```json
{
  "experience_multiplier": {
    "beginner": 1.4,
    "intermediate": 1.0,
    "advanced": 0.75
  },
  "task_type_multiplier": {
    "concept_review": 0.8,
    "practice": 1.0,
    "mock_interview": 1.3,
    "project": 1.5
  },
  "cognitive_load_multiplier": {
    "1": 0.75,
    "2": 0.9,
    "3": 1.0,
    "4": 1.15,
    "5": 1.3
  }
}
```

These multipliers live in deterministic configuration, not in prompts. They can be tuned without changing orchestration code.

## Phase 2: Simple Per-User Calibration

After enough completions, the system learns category multipliers from telemetry.

```json
{
  "user_duration_multipliers": {
    "dynamic_programming": 1.35,
    "arrays": 0.85,
    "system_design": 1.2
  }
}
```

The drift classifier (see `07-telemetry-and-drift.md`) detects `duration_underestimate` or `duration_overestimate` deterministically, and the calibration engine updates these multipliers.

## Phase 3: Pooled Model

After meaningful cross-user data and explicit opt-in, a pooled model can be considered.

Potential features:

- Task category.
- Task type.
- Cognitive load.
- Experience level.
- Scheduled time of day.
- Day of week.
- Recent completion rate.
- Historical category multiplier.

Pooled models still feed deterministic schedulers, never replace them.

## Phase 4: Per-User Model

A per-user model is only considered for power users.

Suggested thresholds before training:

- 200+ completed tasks.
- 30+ completions in a category.
- Stable behavior across multiple weeks.

A per-user model trained on fewer than ~50 tasks is likely to overfit because data is sparse across categories, days, and times.

## Why This Sequencing

- Phase 1 keeps duration estimates explainable and cheap.
- Phase 2 personalizes without privacy cost.
- Phase 3 unlocks cross-user signal under explicit consent.
- Phase 4 is a power-user feature, not an MVP requirement.

Skipping straight to per-user models before Phase 1 is stable would create estimates that are hard to debug and easy to break.

## Related Docs

- `07-telemetry-and-drift.md`
- `09-cost-and-metrics.md`
- `10-mvp-roadmap.md`
- `../decisions/ADR-0004-no-per-user-ml-model-in-mvp.md`
- `../specs/telemetry.schema.md`
