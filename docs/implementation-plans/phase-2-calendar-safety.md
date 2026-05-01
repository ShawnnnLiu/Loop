# Phase 2: Calendar Safety

## Goal

Implement safe calendar preview, approval, write, verification, duplicate prevention, and rollback. Preserve the invariant that no calendar write occurs without explicit approval.

## Required Docs

- `../../AGENTS.md`
- `../axioms/05-scheduler-policy.md`
- `../axioms/06-calendar-safety.md`
- `../specs/scheduler-output.schema.md`
- `../specs/approval-event.schema.md`
- `../specs/calendar-event-mapping.schema.md`
- `../decisions/ADR-0002-preview-only-calendar-writes.md`

## Deliverables

- Approval event creation for draft schedules.
- Payload hash verification before writes.
- Calendar Write Manager with dry-run, write, verify, and rollback operations.
- Calendar event metadata with `run_id`, `plan_version`, and `task_id`.
- Calendar event mapping persistence.
- Duplicate detection by metadata.

## Acceptance Criteria

- Scheduler cannot call calendar APIs.
- Calendar Write Manager rejects missing `approval_event_id`, `run_id`, `plan_version`, or `task_id`.
- Writes only occur when `approved_payload_hash` matches the draft payload.
- Each write is verified by reading back the external event.
- Rollback uses stored `calendar_event_mapping`.
- Calendar duplicate event rate remains 0 in tests.

## Explicit Non-Goals

- Silent writes.
- Autonomous replanning.
- Offline calendar sync.
- Heuristic drift responses.

## Test Expectations

- Approval required tests.
- Dry-run tests.
- Duplicate prevention tests.
- Verification failure tests.
- Rollback success and rollback failure tests.
- Tests for metadata on external event payloads.
