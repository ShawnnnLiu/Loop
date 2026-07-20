# Calendar Grid Rework — Overview

Status: **complete** — implemented and merged to `main` (PR #43).

Three UX upgrades to the Week hour grid (`frontend/src/screens/ScheduleReview.tsx`),
frontend-only, no backend/contract/schema change:

1. **Full-day scrollable axis** — the grid shows all 24 hours and scrolls
   vertically, so busy blocks outside the user's working hours are visible.
2. **Current-time indicator** — a Notion/Google-Calendar-style "now" line on
   today's column.
3. **Block details popover** — clicking a block opens a small card with the
   full (untruncated) title, times, status, and a slot for a future
   description.

Planned 2026-07-19; all references verified the same day against the working
tree (branch `user-plan-direction` — see the concurrency section, this
matters).

## Corrected diagnosis (why busy blocks are invisible today)

The observed behavior is "the grid doesn't show events earlier than my
onboarding start time". The actual mechanics are slightly different, and the
difference changes the fix:

- The grid's vertical axis is **hardcoded**, not onboarding-derived:
  `START_HOUR = 8` / `END_HOUR = 23` at `ScheduleReview.tsx:51-52`, with
  `GRID_TOP`/`GRID_BOT` (`:56-57`) clamping drag to the same range
  (`onMove`, `:447`).
- The onboarding working-time bounds live on the profile as
  `hard_constraints.no_events_before` / `no_events_after` (HH:MM strings —
  backend `contracts/user_profile.py:65-66`, frontend `api/types.ts:18-19`).
  The Week screen **already fetches the profile** (`api.me()` →
  `setProfile`, `ScheduleReview.tsx:184-186`) but only passes it to the Plan
  board's target pill — the grid never reads it.
- The server-side free/busy fetch has **no hour-of-day clamp**: it queries
  `[now, now + timeline_weeks * 7d)` whole-days
  (`app/web/calendar_service.py:110-137`) and `/api/draft` includes the full
  list (`routes_cycle.py:453-457`). So a 6am busy block already arrives at
  the client — the grid just computes a negative `topPx` (`:114`) for it and
  paints it off-axis (absolutely positioned above the column, under the
  sticky header). Same for blocks past 11pm, off the bottom.
- Consequence worth fixing regardless: a user whose allowed window starts
  before 8am (e.g. `no_events_before: "06:00"`) gets scheduler-placed blocks
  at 6–8am that render off-axis, and the hardcoded drag clamp makes those
  perfectly valid slots **unreachable by drag**. The hardcoded axis fights
  the profile in both directions.

So: no data plumbing is needed anywhere. This is a pure rendering/interaction
rework of one screen plus new pure helpers.

## Decisions (locked 2026-07-19)

1. **Fixed 24h axis** (0:00–24:00), not a profile-cropped axis. `HOUR_PX`
   stays 46 → grid body is 1104px tall inside the existing scroll container
   (`.sched-scroll` is already `overflow: auto`, `tokens.css:615-619`, and
   the day header is already sticky, `:620-627`). Rejected: cropping the
   axis to allowed-hours-±-padding — recomputes geometry per user, breaks
   the "scroll to check anything" ask, and saves nothing.
2. **Initial scroll** puts the working window in view: on first grid render
   scroll to ~30min above `min(allowed start, now)` when today is visible,
   else the allowed start. Auto-scroll fires **once per screen mount**, never
   on week paging or view-toggle round-trips (don't yank the user's scroll).
3. **Off-hours shading**: the regions before `no_events_before` and after
   `no_events_after` get a subtle full-width tint band so the working window
   stays visually primary. Fallback when the profile is unavailable: shade
   outside 08:00–23:00 (yesterday's visual bounds).
4. **Drag clamp follows the profile**, not the axis: dragging is clamped to
   the allowed window (fallback 08:00–23:00). The server remains the only
   authority — every drop is still re-validated (`OUTSIDE_ALLOWED_HOURS`,
   `scheduler/adjustment.py`) — the clamp is UX courtesy so users can't drop
   where the server must reject. This *widens* reachability for early/late
   allowed windows and keeps the existing behavior otherwise.
5. **Cross-midnight busy intervals get split** into per-day segments clipped
   to [0:00, 24:00). Today a 11pm–1am event overflows the column bottom
   (invisible pre-rework only because the axis ends at 11pm). Draft entries
   never cross midnight (scheduler places within allowed hours), so only
   busy intervals need splitting.
6. **Now line**: today's column only, red (`#c0492f`, the convention color —
   Notion/GCal both use red), 2px line + dot at the column's left edge,
   ticking on a 30s interval. Rendered only when today's column is on
   screen, which by the rolling-window construction means
   `windowMs === anchorMs`. "Now" is the **user's wall clock**: derived from
   `Date.now()` + the draft's own offset (`offsetMinutes`,
   `lib/datetime.ts:53-58`) — never the browser timezone, matching the
   grid's as-written convention. The grid only renders when
   `blocks.length > 0` (`ScheduleReview.tsx:267-276`), so `blocks[0].offset`
   is always available.
7. **Popover trigger**: on editable blocks, a pointerup with no effective
   move — exactly the existing "no move" branch in `onUp`
   (`ScheduleReview.tsx:462-465`) — opens the popover; drag semantics are
   untouched (any snap-level move is a drag, not a click). Read-only task
   blocks and busy blocks get a plain `onClick`.
8. **Popover content is existing client data only**: full title, day + time
   range + duration, an honest status line mirroring the block's legend
   state, and category/focus level when `/api/today` facts carry them
   (non-editable modes; silently absent otherwise). A `description` slot
   renders only when non-null — **it is always null today**; no backend
   field is added by this plan.
9. **Busy-block popover cannot show event names, by design.** Free/busy is
   opaque ranges only (axiom 06 / no-raw-calendar-content;
   `calendar_service.py:82-86`). The popover says so honestly ("Loop only
   reads busy times — event details stay in your calendar").
10. **Plan board view is out of scope.** The rail already lists full titles;
    the board/rail (`WeekPlanView.tsx`, `lib/weekplan.ts`) is untouched
    except for exporting the existing `fmtDur` helper.

## Concurrency guardrails — user-plan-direction runs in parallel

`docs/implementation-plans/completed/user-plan-direction/` is being executed
concurrently in a different session **in this same checkout** (branch
`user-plan-direction` has its uncommitted work). Hard rules:

- **This plan folder is the only thing created now** (new untracked
  directory — zero conflict surface).
- Execution happens later, on branch **`calendar-grid-rework` cut from
  `main`** after this folder merges. If the folder is missing from `main`,
  stop and ask.
- Files this rework may touch (exhaustive):
  - `frontend/src/screens/ScheduleReview.tsx`
  - `frontend/src/lib/gridtime.ts` + `gridtime.test.ts` (new)
  - `frontend/src/lib/popover.ts` + `popover.test.ts` (new)
  - `frontend/src/lib/weekplan.ts` (export `fmtDur` only — one line)
  - `frontend/src/components/BlockPopover.tsx` (new)
  - `frontend/src/styles/tokens.css` (append within the grid section)
- Files this rework must **not** touch (the concurrent split's blast
  radius, plus its backend surface): anything under `backend/`, `schemas/`,
  `docs/specs/`; `frontend/src/screens/Onboarding.tsx`,
  `frontend/src/lib/intake.ts`, `frontend/src/api/types.ts`,
  `frontend/src/api/client.ts`. Everything the grid needs from
  `api/types.ts` (`UserProfile.hard_constraints`, `DraftView.free_busy`)
  already exists — read-only imports are fine.

## Phases

| Phase | Doc | Content |
| --- | --- | --- |
| G-A | `01-full-day-grid.md` | 24h axis, off-hours shading, profile-derived drag clamp, busy segment splitting, initial scroll |
| G-B | `02-now-indicator.md` | Now line + dot on today's column, 30s tick |
| G-C | `03-block-popover.md` | Click-vs-drag disambiguation, `BlockPopover` component, placement helper |
| G-D | `04-gates-and-smoke.md` | Frontend gates, real-browser smoke checklist, graphify update |

Sizing and the kickoff prompt live in `SPLITS.md` (single split, G-A→G-D).

## Reference table (verified 2026-07-19)

If a cited line number no longer matches, trust the named symbol over the
line number and note the drift in the session summary.

| Symbol | Location |
| --- | --- |
| `START_HOUR`/`END_HOUR`/`HOURS`/`HOUR_PX`/`SNAP`/`GRID_TOP`/`GRID_BOT` | `frontend/src/screens/ScheduleReview.tsx:51-57` |
| `toBlocks` / `toBusy` | `ScheduleReview.tsx:88-112` |
| `topPx` / `heightPx` / `clamp` | `ScheduleReview.tsx:114-116` |
| profile fetch (`api.me()` → `setProfile`) | `ScheduleReview.tsx:179-187` |
| `nowMs` state + 30s interval (sync-age only today) | `ScheduleReview.tsx:254-260` |
| empty-draft early return (guarantees `blocks[0]`) | `ScheduleReview.tsx:267-276` |
| window/anchor math (`anchorMs`, `weeks`, `windowMs`) | `ScheduleReview.tsx:281-297` |
| drag geometry + clamp (`onDown`/`onMove`/`onUp`) | `ScheduleReview.tsx:418-489` (clamp `:447`, no-move branch `:462-465`) |
| grid render (gutter, lines, busy, blocks) | `ScheduleReview.tsx:795-887` |
| grid CSS section | `frontend/src/styles/tokens.css:600-770` |
| `offsetMinutes` / `todayDayMs` / `windowStartMs` | `frontend/src/lib/datetime.ts:53-72` |
| `stackByDay` | `frontend/src/lib/stack.ts` |
| `fmtDur` (module-local, to export) | `frontend/src/lib/weekplan.ts:199-203` |
| `todayFacts` (category/focus per task) | `frontend/src/lib/weekplan.ts:63-76` |
| `HardConstraints` (frontend type) | `frontend/src/api/types.ts:17-23` |
| `hard_constraints` HHMM fields (backend truth) | `backend/src/agentic_calendar/contracts/user_profile.py:60-78` |
| server free/busy fetch (no hour clamp, user-tz restamp) | `backend/src/agentic_calendar/app/web/calendar_service.py:70-137` |
| `/api/draft` free/busy wiring | `backend/src/agentic_calendar/app/web/routes_cycle.py:453-457` |
| `OUTSIDE_ALLOWED_HOURS` | `backend/src/agentic_calendar/contracts/reason_codes.py`, enforced in `scheduler/adjustment.py` |
