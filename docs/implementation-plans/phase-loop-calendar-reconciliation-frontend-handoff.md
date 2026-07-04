# Handoff: Calendar Reconciliation — Frontend (R-e)

**For a fresh context window.** The backend for inbound calendar reconciliation is **done, committed, and green**; this is the remaining SPA work. Read this top-to-bottom — it is self-contained.

## Context (what already exists)

Inbound reconciliation = detect when the user edits Loop's own events directly on their Google Calendar (move / resize / delete) and **adopt valid edits** into the in-app schedule, flag the rest. It is **deterministic, read-only against the calendar, and opt-in / off by default** (axiom 06: the in-app schedule is the system of record).

- **Spec:** `docs/specs/calendar-reconciliation.schema.md`
- **Plan:** `docs/implementation-plans/phase-loop-calendar-reconciliation.md`
- **Branch:** `loop-calendar-reconciliation` (backend R-a..R-d committed; PR open against `main`). Do the frontend on this branch.
- **Backend is complete:** contracts, mapping store, the `reconcile()` engine, the opt-in flag, and the HTTP endpoints all exist and pass `make lint/typecheck/boundaries/schema-check` + 2463 tests. **Do not touch backend** except to read it.

## Your task

Make the feature usable in the React SPA (`frontend/`): TS types, API client methods, an opt-in toggle, and surfacing the reconcile outcome on the Week screen. Nothing more — the deferred items at the bottom are **not** frontend work.

## Backend API contract (exact — this is what you call)

All under `/api`, session-authed, same `request()` helper in `src/api/client.ts`.

1. **`GET /api/me`** — now returns an added field:
   ```ts
   inbound_calendar_sync_enabled: boolean  // default false
   ```
2. **`POST /api/calendar-sync`** body `{ "enabled": boolean }` → returns the refreshed **MeResult** (so you can read back `inbound_calendar_sync_enabled`).
3. **`POST /api/reconcile`** (no body) → returns a **`CalendarReconciliationResult`** (below). Notes:
   - **409** (`CycleError`) if there is **no active plan** — only call it when a plan is active/written.
   - When the opt-in is **off**, it returns `200` with `outcome: "sync_disabled"` and `deltas: []` (after the active-plan check). So: only call it when `me.inbound_calendar_sync_enabled === true` **and** a plan is active.
   - It is **read-only** against the calendar and never writes. On an `adopted`/`mixed` outcome the **draft changed** → refetch the Week draft (`GET /api/draft`) so the grid shows the adopted times.

### `CalendarReconciliationResult` shape

```jsonc
{
  "run_id": "run_...",
  "plan_version": "plan_004",
  "reconciled_at": "2026-06-23T09:05:00-07:00",
  "target_calendar_id": "gcal_dedicated_abc",
  "outcome": "mixed",                       // sync_disabled | deferred | no_change | adopted | flagged | mixed
  "adopted_draft_schedule_id": "draft_017", // non-null iff outcome is adopted|mixed
  "deltas": [
    {
      "task_id": "dp_002",
      "calendar_event_id": "gcal_evt_abc123",   // null only when deleted
      "change_type": "moved",                    // unchanged | moved | resized | deleted
      "recorded_start": "2026-06-23T19:00:00-07:00",
      "recorded_end":   "2026-06-23T20:30:00-07:00",
      "observed_start": "2026-06-24T19:00:00-07:00", // null when deleted
      "observed_end":   "2026-06-24T20:30:00-07:00", // null when deleted
      "disposition": "adopted",                  // unchanged | adopted | rejected | flagged_deleted
      "reason_code": null                        // null for adopted/unchanged; a placement code for rejected; EXTERNAL_EVENT_DELETED for flagged_deleted
    }
  ]
}
```

Rejected `reason_code` is one of the drag-to-adjust placement codes already in the app: `NO_VALID_CONTIGUOUS_BLOCK`, `OUTSIDE_ALLOWED_HOURS`, `DAILY_LOAD_EXCEEDED`, `DEPENDENCY_BLOCKED`. (The existing `ScheduleReview` violation banner already renders these for drag moves — reuse that phrasing.)

## TS types to add (`frontend/src/api/types.ts`)

Add the `MeResult` field and these mirrors (string-union enums, matching the repo's existing style):

```ts
export interface MeResult {
  // ...existing fields...
  inbound_calendar_sync_enabled: boolean
}

export type CalendarEditType = 'unchanged' | 'moved' | 'resized' | 'deleted'
export type ReconciliationDisposition = 'unchanged' | 'adopted' | 'rejected' | 'flagged_deleted'
export type ReconciliationOutcome =
  | 'sync_disabled' | 'deferred' | 'no_change' | 'adopted' | 'flagged' | 'mixed'

export interface CalendarEventDelta {
  task_id: string
  calendar_event_id: string | null
  change_type: CalendarEditType
  recorded_start: string
  recorded_end: string
  observed_start: string | null
  observed_end: string | null
  disposition: ReconciliationDisposition
  reason_code: ReasonCode | null
}

export interface CalendarReconciliationResult {
  run_id: string
  plan_version: string
  reconciled_at: string
  target_calendar_id: string
  outcome: ReconciliationOutcome
  adopted_draft_schedule_id: string | null
  deltas: CalendarEventDelta[]
}
```

## API client to add (`frontend/src/api/client.ts`)

```ts
reconcile: () => request<CalendarReconciliationResult>('POST', '/reconcile', {}),
setCalendarSync: (enabled: boolean) =>
  request<MeResult>('POST', '/calendar-sync', { enabled }),
```
Add a couple of cases to `src/api/client.test.ts` following the existing fetch-mock pattern (assert method/path/body).

## House conventions (follow these — they are enforced)

- **vitest runs in Node, no jsdom/testing-library.** Screens are **not** unit-tested. Put any non-trivial decision logic in a pure `frontend/src/lib/*.ts` with a `*.test.ts` (see `src/lib/review.ts` / `review.test.ts`, `src/lib/approval.ts`). Keep screens thin.
- **Server is the source of truth.** Re-render from a server refetch after a mutation; never optimistic-guess (see how `ScheduleReview`/`Today` refetch).
- **No-BS / honest copy** (a hard project axiom): never claim success you don't have. For `rejected`/`flagged_deleted`, say what didn't apply — do NOT imply the calendar was changed back (the engine never rewrites the user's calendar). Mirror the careful tone in `src/lib/approval.ts` (`writeFailureMessage`) and `src/lib/review.ts` (the `failed` banner).
- **No new dependencies** without asking. **No fake/mock data** in the UI.

## Suggested UI (minimal, usable)

1. **Opt-in toggle.** Recommended home: the **Tuning** screen (`src/screens/Thresholds.tsx`) — add a small "Adopt my Google Calendar edits" switch. It needs `me.inbound_calendar_sync_enabled` (fetch `/api/me` or thread it down from `App.tsx`, which already loads `me`), and calls `api.setCalendarSync(...)`. Off by default; copy should explain it's opt-in and that Loop only reads its own events.
2. **Trigger + surfacing on the Week screen** (`src/screens/ScheduleReview.tsx`). The screen already renders a **read-only "scheduled week"** state when the plan is active (`reviewMode(status) === 'written'`, from `src/lib/review.ts`). In that state, when the opt-in is on, run `api.reconcile()` and surface the outcome as a banner:
   - `adopted` / `mixed` → "N calendar edit(s) adopted" + **refetch the draft** so the grid shows the new times.
   - `flagged` → "N edit(s) couldn't be applied" (list rejected reason_codes / deletions); offer the existing path to rebuild a plan.
   - `mixed` → both.
   - `sync_disabled` / `deferred` / `no_change` → render nothing.
   - Map `delta.task_id` → title via the Week screen's existing `DraftView.task_titles`.
   - Put the outcome→banner decision in a pure tested `src/lib/reconcile.ts` (e.g. `reconcileBanner(result)` returning `{tone, title, sub}` + counts), mirroring `reviewBanner` in `lib/review.ts`.

### One UX decision to make (or ask the user)

How to trigger the pull on the Week screen:
- **(A, recommended) auto-reconcile on mount** when active + opt-in on — matches the spec's "on-demand pull on Today/Week," zero extra clicks. It mutates on load, but only when opted in and only adopts *valid* edits, so it's safe.
- **(B) explicit "Check for calendar edits" button** — more conservative, no surprise mutations on navigation.

Default to (A) unless the user prefers (B).

## Verify before done

```bash
cd frontend
npm run typecheck && npm run lint && npm run test && npm run build
```
All must pass. (Backend is already green; you won't run backend checks unless you touch backend, which you shouldn't.)

## Do NOT do (deferred backend follow-ons, not frontend)

- Feeding rejected/deleted deltas into the drift classifier's `external_conflict_task_ids` (needs a persisted conflict signal; calibration-sensitive).
- Implicit reconcile pre-steps before `/propose` and `/checkin` (the explicit endpoint already makes the feature usable).
- Any auto-cancellation of a task when its calendar event was deleted (axiom 06: cancellation-on-delete is itself opt-in).
