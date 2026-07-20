# G-A — Full-Day Scrollable Grid

Goal: the hour grid spans 0:00–24:00, scrolls vertically, shades the hours
outside the user's allowed window, clamps drag to the *profile's* allowed
window instead of the hardcoded 8a–11p, and renders cross-midnight busy
intervals correctly. No API or backend change.

## 1. New pure module: `frontend/src/lib/gridtime.ts`

React-free and unit-tested, same split as `lib/stack.ts` / `lib/weekplan.ts`.
All day-minute values are minutes-of-day in the user's wall clock (the grid's
existing convention).

```ts
/** "07:30" -> 450; null for anything unparseable. */
export function parseHHMM(s: string): number | null

/** The user's allowed scheduling window in minutes-of-day.
 *  Falls back to { start: 480, end: 1380 } (the pre-rework visual bounds)
 *  when the profile is null or either bound fails to parse. */
export function allowedWindowMin(
  profile: UserProfile | null,
): { start: number; end: number }

/** Split busy intervals that cross midnight into per-day segments, each
 *  clipped to [0, 1440]. Single-day intervals pass through unchanged.
 *  An interval spanning >2 days yields one segment per day. */
export function splitBusySegments(
  busy: { dayMs: number; startMin: number; durMin: number }[],
): { dayMs: number; startMin: number; durMin: number }[]

/** Minutes-of-day of `nowMs` in the user's wall clock (ISO offset string,
 *  same source as todayDayMs). */
export function nowMinutesOfDay(nowMs: number, offset: string): number

/** Where to scroll on first render, in minutes-of-day: ~30min above
 *  min(allowed start, now) when today is in view, else above the allowed
 *  start. Clamped to >= 0. */
export function initialScrollMin(
  allowedStart: number,
  nowMin: number | null,
): number // Math.max(0, Math.min(allowedStart, nowMin ?? allowedStart) - 30)
```

Import `UserProfile` from `../api/types` (read-only — see the overview's
concurrency rules) and `offsetMinutes`/`DAY_MS` from `./datetime`.

Implementation notes:

- `parseHHMM`: strict `^(\d{2}):(\d{2})$`, hours 0–23, minutes 0–59.
- `allowedWindowMin` must also fall back when `start >= end` after parsing
  (the backend validator forbids it, but the helper must not trust that).
- `splitBusySegments`: for a segment starting at `startMin` with `durMin`
  running past 1440, emit `[startMin, 1440)` on `dayMs` and recurse the
  remainder onto `dayMs + DAY_MS` at `startMin = 0`. Drop zero-length
  segments.
- `nowMinutesOfDay`: `Math.floor(((nowMs + offsetMinutes(offset) * 60_000) % DAY_MS) / 60_000)`
  — `nowMs` is always positive, so no negative-modulo handling is needed;
  say so in a comment only if a test pins it.

## 2. Screen changes (`ScheduleReview.tsx`)

- Constants: `START_HOUR = 0`, `END_HOUR = 24` (keep the names; `HOURS`,
  `GRID_TOP`, `GRID_BOT` derive as today). `HOUR_PX` stays 46. The hour
  gutter now renders 24 labels (`fmtMinutes` gives `12a`, `1a`, …).
- **Drag clamp**: compute `const allowed = allowedWindowMin(profile)` once
  per render; in `onMove` replace the `GRID_TOP`/`GRID_BOT` clamp with
  `clamp(…, allowed.start, allowed.end - g.dur)`. `GRID_TOP`/`GRID_BOT`
  keep their axis meaning (0/1440) for geometry only.
- **Busy segments**: wrap the existing projection —
  `splitBusySegments(toBusy(view))` — *before* the per-window filter, so a
  midnight-crossing segment lands in the right day column (each segment
  carries its own `dayMs`). Stacking keys stay `busy${i}` over the split
  result; the stack input at `:393-399` needs no change beyond consuming
  the split list.
- **Off-hours shading**: inside `.sched-cols`, before the hlines, render two
  full-width bands with class `sched-offhours` (`pointer-events: none`):
  top band `[0, allowed.start)`, bottom band `[allowed.end, 1440)`. Skip a
  band whose height is 0. Blocks render above the bands (bands carry no
  z-index; keep them first in DOM order).
- **Initial scroll**: a `useEffect` keyed on the grid actually rendering
  (view kind `grid`, `view` non-null) that runs **once per screen mount**
  (a `useRef` flag, same pattern as `reconciledRef`): set
  `sched-scroll`'s `scrollTop` to
  `(initialScrollMin(allowed.start, todayVisible ? nowMin : null) / 60) * HOUR_PX`.
  The scroll container needs a ref; `todayVisible` is `windowMs === anchorMs`
  (see G-B). Switching Plan→Grid later must not re-scroll.

## 3. CSS (`tokens.css`, append inside the grid section)

```css
/* Hours outside the user's allowed window (hard_constraints). Imported busy
   blocks may live here; Loop never schedules here. */
.sched-offhours {
  position: absolute;
  left: 0;
  right: 0;
  background: rgba(108, 120, 134, 0.06);
  pointer-events: none;
}
```

(Reuses the muted gray family the busy styling already uses; no new tokens.)

## 4. Tests (`frontend/src/lib/gridtime.test.ts`)

Vitest, deterministic, house pattern (see `stack.test.ts`):

- `parseHHMM`: valid values incl. `"00:00"`/`"23:59"`; rejects `"7:30"`,
  `"24:00"`, `"aa:bb"`, `""`.
- `allowedWindowMin`: real profile values; null profile → fallback; one
  unparseable bound → fallback; inverted bounds → fallback.
- `splitBusySegments`: single-day passthrough; 23:00–01:00 → two segments
  (23:00–24:00 on day N, 00:00–01:00 on day N+1); an interval spanning two
  midnights → three segments; zero-length results dropped.
- `nowMinutesOfDay`: `Z`, positive and negative offsets; a case where the
  offset pushes the wall clock across midnight relative to UTC.
- `initialScrollMin`: now before allowed start; now after; null now; clamp
  at 0 for an allowed start earlier than 00:30.

No existing frontend test pins the grid geometry (verified 2026-07-19 —
the only `8a` hit is a `fmtMinutes` label test in `datetime.test.ts:131`).

## Acceptance

- A busy block at 6:00–7:00am renders inside the 6am row of the correct day
  and is reachable by scrolling; same for one at 11:30pm.
- A user with `no_events_before: "06:00"` can drag a proposed block to
  6:00am; a drop at a time the server rejects still snaps back with the
  typed reason (unchanged path).
- The off-hours regions are visibly tinted; the working window is not.
- On open, the grid is scrolled to the working window, not to midnight.
