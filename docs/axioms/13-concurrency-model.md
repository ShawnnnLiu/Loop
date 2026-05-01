# 13: Concurrency Model

## Rule

Only one calendar-write transaction per user can be active at a time.

Multiple draft edits can exist, but only one draft can be promoted to active.

## Allowed During Active Write

- Read-only viewing.
- Creating a separate draft.
- Editing a draft.
- Comparing drafts.

## Blocked During Active Write

- Activating another plan.
- Writing another schedule.
- Deleting generated events.
- Mutating the active plan.

## Calendar Write Lock

The Calendar Write Manager acquires `calendar_write_lock` before any write, holds it through verification, and releases it afterwards. The Supervisor must check the lock before routing to anything that would mutate calendar state.

If the Supervisor sees an active lock, it routes to `block_conflicting_calendar_write` and emits a typed `reason_code` for any conflicting request.

## Draft Promotion Rule

Only a draft with all of the following can be promoted to active:

- Validated `task_plan`.
- Successful Scheduler output (no failure `reason_code`).
- A recorded `approval_event` with `approved: true` and matching `approved_payload_hash`.
- No active `calendar_write_lock`.

Any missing condition must produce a typed failure and block promotion.

## Race Conditions

- Two replan requests within the same window: only one acquires the write lock; the other waits and re-evaluates after the first completes.
- User edits a generated event during write verification: mark `user_modified_bool: true` in `calendar_event_mapping` and preserve the user edit.
- Conflict between drift-triggered replan and user-initiated replan: prefer the user request and queue the drift response for the next window.

## Related Docs

- `02-state-machine.md`
- `06-calendar-safety.md`
- `15-plan-versioning-and-diffs.md`
- `16-reliability-patterns.md`
- `../specs/calendar-event-mapping.schema.md`
