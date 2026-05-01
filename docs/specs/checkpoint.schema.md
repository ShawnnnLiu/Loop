# Checkpoint Schema

## Owner

Checkpointing layer.

## Consumers

Recovery flow, audit log, fork operations, debug tooling.

## Purpose

Persist orchestration state at every meaningful transition so the system can resume after failures without corrupting state. Checkpoints also support fork semantics when a user rejects a draft.

## JSON Example

```json
{
  "thread_id": "thread_user_123_2026_05",
  "checkpoint_id": "ckpt_2026_05_04_018",
  "parent_checkpoint_id": "ckpt_2026_05_04_017",
  "state_json": {
    "plan_state": "tasks_validated",
    "plan_version": "plan_004",
    "run_id": "run_2026_05_04_001"
  },
  "metadata_json": {
    "node": "validator",
    "outcome": "valid",
    "reason_code": null
  },
  "created_at": "2026-05-04T17:50:00-07:00"
}
```

## Field Semantics

| Field | Purpose |
| --- | --- |
| `thread_id` | Logical orchestration thread for the user |
| `checkpoint_id` | Stable identifier for the checkpoint |
| `parent_checkpoint_id` | Previous checkpoint, enabling forks and rollbacks |
| `state_json` | Serialized plan and routing state at this point |
| `metadata_json` | Diagnostic metadata, including last node and `reason_code` |
| `created_at` | Timestamp the checkpoint was written |

## Required Checkpoints

The system writes checkpoints after:

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

## Invariants

- Every checkpoint must have a unique `checkpoint_id`.
- `parent_checkpoint_id` must reference an existing checkpoint or be null for the root.
- Checkpoints are append-only and immutable once written.
- `state_json` and `metadata_json` must be valid serialized objects.
- Resume must always pick the latest successful checkpoint for the thread unless an explicit fork is requested.

## Fork Semantics

When the user rejects a plan, the system forks from the prior checkpoint instead of overwriting state. The prior plan remains available for comparison or restoration. See `../axioms/14-checkpointing-recovery.md` and `../axioms/15-plan-versioning-and-diffs.md`.

## Invalid Examples

```json
{
  "checkpoint_id": "ckpt_2",
  "parent_checkpoint_id": "ckpt_does_not_exist"
}
```

Reason: orphan parent reference.

```json
{ "checkpoint_id": "ckpt_3", "state_json": null }
```

Reason: missing serialized state.

## Related Docs

- `../axioms/02-state-machine.md`
- `../axioms/14-checkpointing-recovery.md`
- `../axioms/15-plan-versioning-and-diffs.md`
- `../axioms/16-reliability-patterns.md`
