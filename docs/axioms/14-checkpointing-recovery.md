# 14: Checkpointing and Failure Recovery

## Purpose

Checkpointing allows the system to resume after failures without corrupting state. Every state transition must be recoverable.

## Checkpoint Schema

```text
thread_id
checkpoint_id
parent_checkpoint_id
state_json
metadata_json
created_at
```

See `../specs/checkpoint.schema.md`.

## Checkpoint Timing

The system writes a checkpoint after every meaningful state transition:

- Onboarding completion.
- Syllabus generation.
- Syllabus validation.
- Task planning.
- Task validation.
- Draft schedule generation.
- User approval.
- Calendar write start.
- Calendar write verification.
- Telemetry update.
- Drift classification.

## Mid-Node Crash

If a node crashes before completion, resume from the last successful checkpoint. The failed node may re-execute, so any node with side effects must be idempotent. Calendar writes use `run_id` and `task_id` to detect what already succeeded (see `06-calendar-safety.md`).

## Fork Semantics

If the user rejects a plan, fork from the previous checkpoint instead of overwriting the old plan. This lets the user compare drafts or restore prior versions.

Forks must:

- Preserve `parent_checkpoint_id`.
- Create a new `plan_version` if the fork modifies the plan.
- Never silently discard the prior checkpoint.

## Idempotency Requirements

Nodes that may re-run after a crash must be designed to be idempotent:

- Calendar Write Manager queries by `run_id`/`task_id` before any retry.
- Telemetry ingestion deduplicates by `telemetry_event_id`.
- Validation must not mutate the artifact under test.
- Approval recording must not double-create `approval_event` for the same `approved_payload_hash`.

## Related Docs

- `02-state-machine.md`
- `06-calendar-safety.md`
- `13-concurrency-model.md`
- `15-plan-versioning-and-diffs.md`
- `16-reliability-patterns.md`
- `../specs/checkpoint.schema.md`
