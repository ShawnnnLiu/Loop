# 02: State Machine and Supervisor

## Supervisor Purpose

The Supervisor is the central router. It is a pure deterministic function. It reads partitioned state and returns the next node name. It must not call an LLM. It must not write to the calendar. It must not mutate core plan objects except for routing metadata.

The Supervisor is what prevents the product from becoming an uncontrolled multi-agent system.

## Plan State Enum

```text
onboarding_incomplete
profile_ready
syllabus_draft_created
syllabus_validated
tasks_created
tasks_validated
draft_schedule_created
awaiting_user_approval
calendar_write_approved
calendar_write_in_progress
calendar_write_verified
active_plan
drift_detected
replan_required
error_requires_user
idle
```

## Supervisor Routing Pseudocode

```python
def route(state):
    if state.user_profile.status == "incomplete":
        return "onboarding"
    if state.calendar_write_lock.active:
        return "block_conflicting_calendar_write"
    if state.error_status.requires_user:
        return "approval_or_error_gate"
    if state.draft_schedule.exists and state.approval_status == "pending":
        return "approval_gate"
    if state.drift_summary.exists and not state.drift_summary.processed:
        return "drift_classifier"
    if state.syllabus.status in ["missing", "stale", "invalidated"]:
        return "strategist"
    if state.tasks.status in ["missing", "invalidated"]:
        return "planner"
    if state.tasks.status == "created" and not state.validation.valid:
        return "validator"
    if state.validation.valid and not state.draft_schedule.exists:
        return "scheduler"
    if state.draft_schedule.exists and not state.calendar_written:
        return "approval_gate"
    return "idle"
```

`repair_or_error()` may retry repair at most two times. After retry exhaustion, emit a typed `reason_code` and enter `error_requires_user`.

## Supervisor Mutability Rules

The Supervisor may update:

- `routing_status`
- `last_routed_at`
- `error_status` when routing fails

The Supervisor may not directly mutate:

- `user_profile`
- `syllabus_units`
- `json_tasks` / `task_plan`
- `validated_tasks`
- `draft_schedule`
- `calendar_event_mappings`
- `telemetry_log`

## Invalid Transition Examples

| Current State | Invalid Transition | Reason |
| --- | --- | --- |
| `tasks_created` | `calendar_write_in_progress` | Tasks not validated or scheduled |
| `draft_schedule_created` | `active_plan` | User has not approved calendar write |
| `calendar_write_in_progress` | `planner` | Calendar write lock active |
| `syllabus_invalidated` | `scheduler` | Tasks may be stale |
| `draft_schedule_created` | `calendar_write_in_progress` | Missing `awaiting_user_approval` and `calendar_write_approved` |
| `calendar_write_approved` | (any write) | Missing `approval_event_id` |
| `active_plan` | (mutation in place) | New plan version required |
| `drift_detected` | `calendar_write_in_progress` | Replan, validation, draft schedule, and approval missing |

The state machine must reject every invalid transition with a typed `reason_code`.

## Related Docs

- `01-system-boundaries.md`
- `04-validation-layer.md`
- `06-calendar-safety.md`
- `13-concurrency-model.md`
- `14-checkpointing-recovery.md`
- `15-plan-versioning-and-diffs.md`
- `../specs/approval-event.schema.md`
