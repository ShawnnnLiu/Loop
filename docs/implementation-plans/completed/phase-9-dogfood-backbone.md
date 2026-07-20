# Phase 9: Dogfood Backbone

Status: **complete** — implemented and merged to `main`.

## Goal

Make the system usable end-to-end by one real user — the developer — so the
heuristic priors that every axiom marks as uncalibrated (axiom 07 threshold
honesty) can finally be tuned from lived experience instead of guesswork.

Four gaps block real usage today, and none of them is the frontend: every
store is in-memory (state dies on restart, while calibration needs weeks of
state), the Google Calendar adapter is a stub, there is no composition root
(the supervisor is a routing library and only narrow operator CLIs exist),
and axiom 07's required `drift_threshold_history` change log was never
implemented (so tuning would be a silent code edit, which axiom 07 forbids).

This phase is held until Phase 8 lands real LLM adapters — dogfooding canned
fixture plans would calibrate against fiction. It must never compromise the
calendar-safety or determinism invariants of earlier phases.

## Required Docs

- `../../../AGENTS.md`
- `../../axioms/06-calendar-safety.md`
- `../../axioms/07-telemetry-and-drift.md`
- `../../axioms/13-concurrency-model.md`
- `../../axioms/16-reliability-patterns.md`
- `../../axioms/19-always-online-mvp.md`
- `../../specs/approval-event.schema.md`
- `../../specs/calendar-event-mapping.schema.md`
- `../../specs/telemetry.schema.md`
- `../../decisions/ADR-0002-preview-only-calendar-writes.md`
- `phase-8-llm-eval-observability.md` (must be merged first)

## Deliverables

1. **SQLite persistence behind the existing store Protocols.** A
   `Sqlite*Store` beside each `InMemory*Store`, same Protocol, one injected
   DB file (`sqlite3` is stdlib — no new dependency). Covers at minimum:
   plan versions, approval events, calendar event mappings, telemetry
   events, consent records, data-access audit, accountability stores
   (check-ins, nudges, notification log, recommitment, sponsors), and the
   Phase 8 llm-call log. A tiny stdlib-only connection/schema helper lives
   in `common/`; schemas are deterministic `CREATE TABLE IF NOT EXISTS`
   with a versioned `schema_version` table; WAL mode. In-memory stores
   remain the default for tests.
2. **Composition root.** One application service, outside the region set
   (importlinter treats it like `tools/`), wiring the full loop: supervisor
   routing → llm_nodes → validation → scheduler → planning → approval →
   calendar_writer → telemetry → drift → accountability → consent gate.
   Includes the deferred Phase 7 item: supervisor wiring of
   `REPLAN_REQUIRED` for the recovery `PLANNER_REQUIRED` route. Operator
   surface: `tools/run_cycle.py` (onboard / propose / approve / write /
   ingest / status), module-only like every Phase 7+ CLI.
3. **Real `GoogleCalendarAdapter`.** Implemented against
   `google-api-python-client` (new dependency — requires explicit user
   approval), writing only to a dedicated secondary calendar id from
   config. Every axiom 06 invariant holds: dry-run, duplicate detection by
   `run_id` metadata, verification read-back, rollback via
   `calendar_event_mapping`, `approved_payload_hash` recheck, no raw
   titles/descriptions stored. OAuth credentials and tokens are secrets:
   user-run auth flow, gitignored token path, never committed or logged.
4. **Calibration instrumentation.** (a) `threshold-change-log.schema.md` +
   contract + append-only store implementing axiom 07's
   `drift_threshold_history`, generalized to every tuning knob (field,
   prior value, new value, effective_at, justification, dataset
   reference). (b) One tuning file (`backend/tuning.toml`) loaded by the
   composition root and mapped onto the existing config dataclasses
   (`DriftThresholds`, `CalibrationConfig`, pooled training/serving
   configs, eligibility/refinement configs, policy knobs); defaults stay
   in code, the file overrides, and every applied override change writes a
   change-log entry. (c) `tools/show_thresholds.py`: current effective
   values plus change history.

## Acceptance Criteria

- Every persisted store passes the same test suite as its in-memory twin,
  plus restart-survival round trips (process state rebuilt from the DB).
- A single `run_cycle` invocation can drive onboard → propose → validate →
  schedule → preview without any calendar write; writes still require an
  `approval_event_id` and pass the hash recheck (no invariant is relaxed
  for ergonomics).
- The Google adapter integration tests are recorded/fake-transport only —
  no live API calls in CI; the live smoke test is a documented manual
  operator step against the dedicated calendar.
- Changing any tuning value through the supported path is impossible
  without producing a change-log entry; `show_thresholds` reproduces the
  full history deterministically.
- Drift classification, scheduling, validation, and policy-engine behavior
  are byte-identical under default tuning (regression: existing suites
  green, golden scenarios untouched).

## Explicit Non-Goals

- Any UI (Frontend Stage 0 follows this phase).
- Production persistence (Postgres/Firestore), multi-user auth, deployment
  — SQLite is a single-user MVP choice, not the production story.
- Calibrating the Phase 6b pooled model or 6c power-user gate from solo
  data: single-user dogfooding calibrates the personal deterministic loop
  only (drift thresholds, accountability thresholds, duration multipliers,
  scheduler feel); pooled/gate stay fixture-proven until multi-user data
  exists.
- Autonomous replanning or any relaxation of ADR-0002 preview-only writes.

## Test Expectations

- Shared protocol test suites parametrized over in-memory and SQLite
  implementations for every persisted store.
- Restart-survival tests: write, reopen the DB in a fresh store instance,
  assert full equality of recovered state.
- Composition-root tests driving the full loop against in-memory adapters
  and fixture LLM nodes with deterministic assertions on state transitions
  and typed reason codes.
- Recorded-transport `GoogleCalendarAdapter` tests demonstrating duplicate
  prevention, verification read-back, and rollback against real-shape API
  responses.
- Threshold change-log tests: override applied → entry appended; identical
  overrides → no duplicate entries; history replay is deterministic.
