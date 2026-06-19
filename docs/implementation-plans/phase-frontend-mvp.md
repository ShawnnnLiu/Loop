# Phase: Frontend MVP (deferred items tracker)

## Status

**Stage 0 scheduled after Phase 9; full scope not yet scheduled.** This
document is the single home for user-facing work deferred from Phases 1 and
2. The sequencing decision (2026-06-10) is: Phase 8 (real LLM adapters +
eval) → Phase 9 (`phase-9-dogfood-backbone.md`: persistence, composition
root, real Google adapter, calibration instrumentation) → **Stage 0 below**
(thin local dogfooding app) → 2–4 week dogfood calibration cycle → the full
frontend scope in this document. The "Adapter Work Required Before The UI
Lands" section now lives in Phase 9.

## Stage 0: Thin Local Dogfooding App

A deliberately disposable, single-user, localhost-only surface whose only
job is making daily dogfooding ergonomic enough to sustain for 2–4 weeks.
It is the seed of — not a substitute for — the full frontend below. Branch
`frontend-stage0`, after Phase 9 merges; one commit per part.

- **F0a — Local API over the Phase 9 composition root.** FastAPI + uvicorn
  (new dependencies — require explicit user approval), no auth, localhost
  only, living in the composition-root layer (never inside regions).
  Endpoints mirror `run_cycle`: onboarding (typed validation errors with
  `reason_code`s), propose, draft preview (canonical payload hash shown),
  approve (creates the approval event through the same service — the UI
  structurally cannot bypass `approval_event_id` or the hash recheck),
  write/verify/rollback, telemetry + check-in + recommitment ingestion,
  accountability dashboard, data controls (view/export/delete).
- **F0b — Server-rendered pages.** Jinja2, minimal styling, no JS
  framework: Today view (scheduled tasks with complete/missed actions
  feeding telemetry), Draft review + Approve, Accountability dashboard
  (reusing the `show_accountability` projection), Check-in and
  Recommitment forms, read-only Thresholds page (effective tuning values +
  change history from the Phase 9 change log).
- **F0c — Dogfood protocol.** `docs/dogfooding.md`: run for 2–4 weeks;
  tune only via `tuning.toml` (auto-journaled by the Phase 9 change log);
  weekly review ritual comparing fired drift/accountability events against
  felt reality; adjust one knob at a time with a written justification.

Stage 0 acceptance: every flow it exposes goes through the same services
the operator CLIs use; no axiom 06 invariant is bypassable from the UI; the
app restarts cleanly against the Phase 9 SQLite state.

## Hosted Frontend Follow-ups (deferrals)

The hosted (multi-user, in-browser Google connect) variant of the Stage 0
pages superseded the single-user localhost app. As those pages landed, two
items were deliberately deferred and are tracked here:

- **Motivation-profile capture surface (deferred 2026-06-18).** The onboarding
  form (#1) captures the `user_profile` but deliberately omits the
  `motivation_profile`. Accountability is opt-in on that profile (axiom 21:
  `CycleService.accountability_snapshot` / `_evaluate_accountability` return
  early when it is absent), so the read-only Accountability dashboard (#3)
  ships with an **empty state first** ("Accountability isn't set up — add a
  motivation profile") rather than a capture flow. Decision: empty-state-first
  over (a) extending the onboarding form or (b) a separate setup mini-form —
  smallest change now, dashboard renders nothing live until this lands.
  Follow-up: a motivation-profile entry path (form section or dedicated page)
  that re-onboards with the profile merged in, so the dashboard shows live
  data for a real account. Fields: see `../specs/motivation-profile.schema.md`
  / `contracts/motivation_profile.py`.

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

**Moved to `phase-9-dogfood-backbone.md` (2026-06-10).** The real
`GoogleCalendarAdapter`, persistent storage behind the existing store
Protocols, and the composition root are now Phase 9 deliverables; Stage 0
above depends on them. The Protocol-level interfaces remain unchanged —
only implementations are added.

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
