# Phase: Frontend MVP (deferred items tracker)

## Status

**Not yet scheduled.** This document is a placeholder so that work consciously deferred from Phases 1 and 2 has a single home and does not fall through the cracks. Insert a phase number once the team slots this work into the sequence.

## Goal

Land the user-facing surface that the Phase 1 and Phase 2 axiom roadmaps originally promised but which the corresponding implementation plans deferred so the deterministic core could ship first. After this phase, every flow currently exercised by an operator CLI must also be reachable by an end user, and the system must support real Google Calendar writes — not just the in-memory adapter.

## Required Docs

- `../../AGENTS.md`
- `../axioms/06-calendar-safety.md`
- `../axioms/10-mvp-roadmap.md`
- `../axioms/13-concurrency-model.md`
- `../axioms/16-reliability-patterns.md`
- `../specs/draft-schedule.schema.md`
- `../specs/approval-event.schema.md`
- `../specs/calendar-event-mapping.schema.md`
- `../decisions/ADR-0002-preview-only-calendar-writes.md`

## Deferred From Phase 1

Per `../axioms/10-mvp-roadmap.md` Phase 1 deliverables; explicitly excluded from `phase-1-core-planning.md`:

- **Structured onboarding UI.** Today the user profile, motivation profile, syllabus, and task plan contracts have no user-facing capture surface.
- **Basic draft plan UI.** The deterministic Scheduler emits a draft schedule but there is no user-facing view of it; only golden-test fixtures and operator CLI output exist.

## Deferred From Phase 2

Per `../axioms/10-mvp-roadmap.md` Phase 2 deliverables; explicitly excluded from `phase-2-calendar-safety.md`:

- **Calendar free/busy integration.** `SchedulerInput.calendar_free_busy` exists on the contract but is always empty; no live fetcher populates it. Blocked on the real Google Calendar adapter.
- **Draft schedule preview UI.** Today only the `preview_calendar_write` operator CLI exists.
- **Approval gate UI.** Today only the `approve_calendar_write` operator CLI exists. The gate is fully enforced server-side (`approval_event_id` invariant, mandatory hash recheck under the recorded canonicalization version).

## Adapter Work Required Before The UI Lands

- **Real `GoogleCalendarAdapter`.** `backend/src/agentic_calendar/calendar_writer/google_adapter.py` currently raises `NotImplementedError` for every Protocol method. The four methods (`create_event`, `read_event`, `delete_event`, `query_events_by_metadata`) must be implemented against `google-api-python-client` (or equivalent) without breaking the existing Phase 2 invariants: metadata keys, duplicate detection by `run_id`, verification read-back, and rollback by `calendar_event_id`.
- **Persistent storage.** `InMemoryApprovalEventStore`, `InMemoryCalendarEventMappingStore`, and `InMemoryPlanVersionStore` need persistent backings (SQL/Firestore) so approvals and mappings survive process restart. The Protocol-level interfaces are already in place; only the implementations need to change.

## Acceptance Criteria

- Onboarding flow captures all Phase 1 contracts and runs them through the validation layer; invalid inputs are surfaced with the existing typed `reason_code`s, not as opaque errors.
- Draft schedule preview shows the canonical payload hash to the user before they approve; the approval the user records must carry the same hash plus `hash_canonicalization_version` so the Phase 2 write-time recheck can validate it.
- Approval gate UI cannot bypass `approval_event_id`, the hash check, or the user-modified-bool invariant. Tampering with the in-app draft after approval must invalidate the approval (matching axiom 06's "stale approval problem" guarantee).
- Calendar free/busy comes from the real Google adapter; the Scheduler consumes it without contract changes.
- Every Phase 2 operator CLI flow (preview, approve, write, verify, rollback, reconcile-after-crash) has an equivalent user-facing path.
- A `GoogleCalendarAdapter` integration test (recorded, not live) demonstrates duplicate prevention, verification, and rollback against a real-shape API response.

## Explicit Non-Goals

- Autonomous replanning UI (the system stays preview-only per ADR-0002).
- Native mobile apps (web only for the MVP surface).
- Real-time multi-device sync (the always-online MVP is single-session per user — see `../axioms/19-always-online-mvp.md`).
- Bypassing any axiom 06 invariant for UI ergonomics (e.g., "auto-approve" toggles, "skip verification" debug flags).

## Test Expectations

- E2E tests that drive the full preview → approve → write → verify flow through the UI against the in-memory adapter.
- Adversarial tests that mutate the draft between approval and write and assert the UI surfaces the `APPROVAL_HASH_MISMATCH` reason code rather than silently proceeding.
- Integration tests for `GoogleCalendarAdapter` using a recorded-cassette test harness; no live API calls in CI.
- Persistence tests that prove approvals, mappings, and plan versions survive a simulated process restart.
- Visual-regression tests for the preview and approval screens (axiom 06 requires the user to see exactly what will be written).
