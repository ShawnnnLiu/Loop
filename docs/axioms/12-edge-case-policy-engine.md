# 12: Edge-Case Policy Engine

## Principle

Edge cases must be handled by a deterministic policy engine, not by ad hoc conditionals scattered through the codebase.

Every edge case must produce:

1. A typed `reason_code`.
2. A deterministic next action.
3. A user-facing explanation if needed.
4. A log entry.

## Policy Table

| Condition | Reason Code | Deterministic Action |
| --- | --- | --- |
| Task duration > max session and splittable | `TASK_TOO_LONG_SPLITTABLE` | Split task |
| Task duration > max session and not splittable | `TASK_TOO_LONG_UNSPLITTABLE` | Ask user |
| No free block available this week | `INSUFFICIENT_CAPACITY` | Extend timeline or reduce scope |
| Dependency incomplete | `DEPENDENCY_BLOCKED` | Do not schedule |
| User manually edited generated event | `USER_MODIFIED_EVENT` | Preserve user edit |
| Calendar write failed | `CALENDAR_WRITE_FAILED` | Roll back `run_id` events |
| Validation repair failed twice | `REPAIR_LIMIT_EXCEEDED` | Approval gate |
| Source claim expired | `SOURCE_CLAIM_EXPIRED` | Refresh retrieval or downgrade confidence |
| Calendar event missing after write | `CALENDAR_WRITE_UNVERIFIED` | Retry verification or rollback |
| User changes target role | `PROFILE_MAJOR_CHANGE` | Invalidate syllabus and plan |
| User changes weekly hours | `CAPACITY_CHANGE` | Invalidate schedule |

## Policy-as-Code Example

```yaml
max_validation_repair_attempts: 2
max_scheduler_planner_iterations: 2
max_daily_study_min: 180
max_contiguous_study_min: 120
min_break_between_deep_blocks_min: 30
duration_underestimate_threshold: 1.3
capacity_mismatch_completion_threshold: 0.6
```

These knobs allow behavior to be tuned without rewriting core orchestration code. They live alongside the deterministic services, not inside prompts.

## Profile Update Policy

Profile changes invalidate downstream artifacts only when necessary. The policy also tracks whether the user's accountability contract (motivation profile, check-in cadence, sponsor permissions) needs to be re-reviewed:

| Profile Change | Invalidate Syllabus? | Invalidate Tasks? | Invalidate Schedule? | Invalidate Accountability Contract? |
| --- | --- | --- | --- | --- |
| Weekly hours changed | No | Maybe | Yes | Maybe |
| Target role changed | Yes | Yes | Yes | Maybe |
| Target company added | Maybe | Maybe | Maybe | No |
| Availability changed | No | No | Yes | No |
| Weakness added | Yes | Yes | Yes | No |
| Preferred session length changed | No | Maybe | Yes | No |
| Self-motivation level changed | No | No | No | Maybe |
| Sponsor visibility changed | No | No | No | Yes |
| Pressure tolerance changed | No | No | No | Maybe |
| Weekly check-in disabled | No | No | No | Yes |

Motivation-profile-only changes (for example, toggling sponsor visibility) never invalidate syllabus, tasks, or schedule; they update only the accountability contract. See `21-accountability-layer.md` and `../specs/motivation-profile.schema.md`.

## Syllabus Staleness Triggers

A syllabus must be marked stale when:

- The user changes target role.
- The user changes target company set significantly.
- The user changes timeline significantly.
- The user adds or removes major weaknesses.
- Source claims expire.
- The drift classifier indicates curriculum-level mismatch.

A syllabus must not be regenerated just because the user misses one task.

The MVP path for any of these triggers is **full syllabus regeneration**. Phase 2/3 will introduce a deterministic patch-vs-regenerate classifier that allows narrow profile changes to produce scoped patches instead of full regeneration. See `20-partial-syllabus-regeneration.md`.

## Decision-First, Explanation-Second

Deterministic policy decides the action. The LLM may explain it.

- **Bad**: LLM decides what to do when the user misses a week.
- **Good**: Policy engine selects `reduce_weekly_load`. `UserFacingExplanationNode` explains why.

## Related Docs

- `04-validation-layer.md`
- `05-scheduler-policy.md`
- `07-telemetry-and-drift.md`
- `15-plan-versioning-and-diffs.md`
- `16-reliability-patterns.md`
- `20-partial-syllabus-regeneration.md`
- `21-accountability-layer.md`
- `../specs/motivation-profile.schema.md`
