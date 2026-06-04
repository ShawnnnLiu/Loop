# 16: Deterministic Reliability Patterns

## Principle

Reliability is a system property, not a prompt. The deterministic infrastructure earns trust through typed errors, dry-run previews, rollback paths, and invariant checks.

## Typed Reason Codes

Every failure must carry a typed `reason_code`. The reason code crosses validation, scheduling, telemetry, accountability, and user-visible errors without translation.

### Validation and Scheduling Reason Codes

```text
VALIDATION_FAILED
ORPHAN_DEPENDENCY
CYCLE_DETECTED
NO_VALID_TIME_BLOCK
TASK_TOO_LONG
DEPENDENCY_BLOCKED
USER_APPROVAL_REQUIRED
CALENDAR_WRITE_FAILED
RETRY_LIMIT_EXCEEDED
WEEKLY_LOAD_EXCEEDED
SOURCE_CLAIM_EXPIRED
PROFILE_MAJOR_CHANGE
CAPACITY_CHANGE
```

### Accountability Reason Codes

```text
CHECKIN_DUE
CHECKIN_MISSED
MISSED_TASK_THRESHOLD_REACHED
BEHIND_SCHEDULE_THRESHOLD_REACHED
LOW_COMPLETION_RATE
RECOVERY_PLAN_REQUIRED
SPONSOR_REPORT_PENDING
SPONSOR_PERMISSION_MISSING
SPONSOR_VISIBILITY_VIOLATION
ACCOUNTABILITY_CONTRACT_INACTIVE
ACCOUNTABILITY_MISMATCH
USER_RECOMMITMENT_REQUIRED
```

Every reason code must map to:

- a deterministic trigger;
- a deterministic next action;
- a user-facing explanation;
- a log entry;
- a privacy boundary if external reporting is involved.

Other reason codes are defined in `05-scheduler-policy.md`, `12-edge-case-policy-engine.md`, and `21-accountability-layer.md`.

## LLM Adapter Nodes Only

Only designated nodes may call LLMs:

- `StrategistNode`
- `PlannerNode`
- `ReflectionSummaryNode`
- `UserFacingExplanationNode`

This prevents LLM calls from spreading across the codebase.

## Dry-Run Mode

Every external side effect must support a dry-run stage:

1. Generate dry-run write plan.
2. Validate the dry-run.
3. Show preview to the user.
4. Wait for approval.
5. Execute the write.
6. Verify the write.

If a side effect cannot be previewed, it must not be automated.

## Rollback Requirement

Every automated write must have rollback logic.

- Create calendar events → delete events with the same `run_id`.
- Update calendar events → restore previous values.
- Activate plan → restore previous `active_plan_id`.

If rollback is not defined for an action, the action must not be automated.

## Invariant Checker

After every node, the system must check core invariants:

- `active_plan` has exactly one `plan_id`.
- Every scheduled task belongs to `active_plan`.
- Every calendar event maps to one `task_id`.
- No task depends on a missing task.
- No draft schedule has written calendar events.
- No calendar write occurred without `approval_event_id`.
- Validation did not mutate the artifact under test.
- `task_plan` contains no `prerequisites_met` field.

Invariant violations must be logged with a typed `reason_code` and routed to `error_requires_user`.

## Test Expectations

- Tests must assert typed `reason_code` values, not prompt wording.
- State transition tests cover valid and forbidden paths.
- Validation tests cover schema, graph, coverage, user-fit, and scheduling prechecks.
- Calendar tests cover preview, approval, write, verification, duplicate prevention, and rollback.
- Telemetry and drift tests prove deterministic classification from recorded events.
- LLM-facing code is tested with fixtures and contract checks, not by trusting prompt outputs.

## Related Docs

- `01-system-boundaries.md`
- `04-validation-layer.md`
- `06-calendar-safety.md`
- `12-edge-case-policy-engine.md`
- `13-concurrency-model.md`
- `14-checkpointing-recovery.md`
- `15-plan-versioning-and-diffs.md`
- `21-accountability-layer.md`
- `22-llm-evaluation-and-observability.md`
- `../decisions/ADR-0006-llm-never-touches-the-calendar.md`
- `../golden-test-cases.md`
