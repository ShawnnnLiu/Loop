# Phase Loop: Inbound Calendar Reconciliation (adopt-if-valid, on-demand pull)

Status: **complete** — implemented and merged to `main`.

## Goal

Detect when the user directly edits the app's own events on their dedicated
external calendar (move / resize / delete) and **adopt valid edits** into the
internal schedule while **surfacing invalid edits and deletions as drift** —
without ever writing to the calendar, and gated behind an explicit opt-in so the
app's internal schedule remains the system of record (axiom 06 lines 249–253).

Contract: `docs/specs/calendar-reconciliation.schema.md`.

## Required Docs

- `docs/axioms/06-calendar-safety.md` (in-app source-of-truth + opt-in rule;
  the write/approval gate this work must not touch)
- `docs/axioms/07-telemetry-and-drift.md` (`external_conflict` + replan loop)
- `docs/axioms/13-concurrency-model.md` (`calendar_write_lock`, defer-to-write)
- `docs/axioms/15-plan-versioning-and-diffs.md` (new draft, unchanged plan version)
- `docs/specs/calendar-reconciliation.schema.md` (the contract)
- `docs/specs/calendar-event-mapping.schema.md` (`user_modified_bool`, `scheduled_*`)
- `docs/specs/draft-schedule.schema.md` ("Adjustment" re-validation reused here)
- `docs/specs/drift-event.schema.md` (`DRIFT_EXTERNAL_CONFLICT`)

## Reuse (already in the codebase — do not rebuild)

- `ExternalCalendarAdapter.query_events_by_metadata(run_id)` / `read_event` — the
  privacy-scoped read primitive (returns live `scheduled_start`/`scheduled_end`).
- `DraftSchedule.with_adjustments(new_starts, ...)` — relocate + re-assemble an
  immutable draft (duration preserved).
- `scheduler/adjustment.py` — the hard-rule re-validation (the four placement
  codes) reused verbatim for adopt-if-valid.
- `DriftClassifier` + `external_conflict_task_ids` input + `DRIFT_EXTERNAL_CONFLICT`.
- `CalendarEventMapping.user_modified_bool` — the divergence flag (today always
  `false`; this phase is what sets it `true`).

## Deliverables

Sub-phases are deterministic and land one commit per part.

- **R-a — Contracts.** Pydantic models for `CalendarReconciliationResult` and
  `CalendarEventDelta` (one `contracts/` module); `change_type` / `disposition`
  enums; add `EXTERNAL_EVENT_DELETED` to `contracts/reason_codes.py`. Valid +
  invalid fixtures matching the spec's examples; generated JSON schema.
- **R-b — Mapping mutation.** A `CalendarEventMappingStore` method to update
  `scheduled_start`/`scheduled_end` and set `user_modified_bool=true` (audited,
  analogous to `update_status`; the field is mutable, the status enum is not
  changed). Honor the existing invariant that `user_modified_bool: true` mappings
  are never overwritten silently.
- **R-c — Reconciliation service (deterministic).** `reconcile(run_id)`: gate →
  defer-to-write → pull → diff/classify → whole-placement re-validate →
  adopt-if-valid (new draft via `with_adjustments`, update mappings) /
  flag-as-drift (rejected + deleted). No calendar write under any path.
- **R-d — Opt-in flag + triggers + drift wiring.** `inbound_calendar_sync_enabled`
  (default `false`) on the user record; pull invoked on-demand before
  `/propose`, before `/checkin`, and on the Today/Week reads; rejected/deleted
  deltas fed to the drift classifier's `external_conflict_task_ids`.
- **R-e — Surfacing.** A read projection so the SPA can show "you moved X on your
  calendar — adopted" vs "…conflicts, here's a replan". (Frontend rendering is a
  follow-on; this phase exposes the typed result.)

## Acceptance Criteria

- With the opt-in **off**, every entry point is a no-op (`outcome:
  "sync_disabled"`) and behavior is byte-identical to today.
- A valid external move is adopted: a new immutable `draft_schedule_id` under the
  unchanged `plan_version`, affected mappings updated with
  `user_modified_bool=true`, **zero** calendar API writes, no `approval_event`
  minted, state stays `ACTIVE_PLAN`.
- An invalid external move (overlap / outside hours / daily-load / dependency) is
  **not** adopted; the prior internal time stands, the mapping is flagged, and a
  `DRIFT_EXTERNAL_CONFLICT` event is emitted carrying the hard-rule code.
- An externally deleted event is flagged + drift-routed; never silently re-created
  or silently cancelled.
- Reconciliation defers (no-op) while a write is in progress / the lock is held.
- Reads are metadata-scoped to the dedicated calendar; no raw event text is read
  or stored.

## Explicit Non-Goals

- No webhooks / `events.watch` / push notifications (follow-on).
- No `events.list` + `syncToken` incremental sync (follow-on; current
  `list_events` has no `syncToken` param).
- No automatic calendar writes to "fix" a rejected edit — surfacing only.
- No auto-cancellation of a task on external delete (itself opt-in per axiom 06).
- No change to the approval / `approved_payload_hash` write gate.
- No LLM involvement in any disposition.

## Test Expectations

- Deterministic diff/classify from recorded vs observed times: `unchanged`,
  `moved`, `resized`, `deleted`.
- Adopt-if-valid: asserts new draft id, mapping updates + `user_modified_bool`,
  and **no** adapter write call (spy/fake adapter).
- Reject paths: each of the four hard-rule codes, plus the deletion path, each
  emits the typed `reason_code` and a `DRIFT_EXTERNAL_CONFLICT` event.
- Opt-in off → no-op; defer-to-write → no-op.
- Privacy: the adapter is queried only with this run's metadata; a foreign /
  untagged event on the calendar is ignored.
- Invalid fixtures from the spec produce the expected structured violations.
- Exercise the relevant scenarios in `docs/golden-test-cases.md` if reconciliation
  is added there.
