# ADR-0002: Preview-Only Calendar Writes

## Status

Accepted

## Context

Calendar writes affect real user commitments. Silent or poorly traced writes can create duplicate events, missed obligations, and loss of trust.

## Decision

All calendar changes are preview-only until explicit approval. The Scheduler emits draft schedules only. Calendar Write Manager is the only writer and requires `approval_event_id`, `approved_payload_hash`, `run_id`, `plan_version`, and `task_id`.

## Consequences

The flow has more steps, but every write is auditable, verifiable, and reversible. UX must make preview and approval fast without weakening the invariant.

## Related Docs

- `../axioms/06-calendar-safety.md`
- `../specs/approval-event.schema.md`
- `../specs/calendar-event-mapping.schema.md`
