# G-B — Current-Time Indicator

Goal: a Notion/Google-Calendar-style "now" line on today's column that stays
current while the tab is open. Depends on G-A only for `nowMinutesOfDay`.

## 1. When it renders

Only when today's column is on screen. The rolling windows are anchored on
today (`anchorMs` is column 0 of the anchor window,
`ScheduleReview.tsx:281-297`), so today is visible **iff
`windowMs === anchorMs`** — paging to any other window hides the line. No
date-range arithmetic beyond that equality.

## 2. Time source and tick

- "Now" is the user's wall clock: `nowMinutesOfDay(nowMs, blocks[0].offset)`
  (G-A helper). The draft's own offset is the same source `anchorMs` already
  uses — never the browser timezone. The grid renders only after the
  empty-draft early return (`:267-276`), so `blocks[0]` exists.
- Reuse the existing `nowMs` state (`:255`) but make its 30s interval
  **unconditional** (mount-scoped), instead of gated on `syncedAt != null`
  (`:256-260`). One interval then serves both the sync-age label and the
  now line. Side benefit: a tick after midnight re-renders, `anchorMs` is
  recomputed from `Date.now()` per render, and the window re-anchors on the
  new day without a reload.

## 3. Visual

Inside `.sched-cols`, absolutely positioned, `pointer-events: none`:

- a 2px horizontal line spanning **today's column only** — today is column 0
  of the anchor window, so `left: 0`, `width: ${100 / 7}%`;
- a 7px filled dot centered on the line at the column's left edge;
- color `#c0492f` (the app's existing red; also the Notion/GCal convention
  for the now line);
- `top: (nowMin / 60) * HOUR_PX` (with G-A, `topPx(nowMin)` since
  `GRID_TOP` is 0);
- `z-index` between static blocks and a dragging block (dragging is 50 —
  use 30) so the line reads above resting blocks but never above the block
  being dragged.

CSS classes `sched-now` / `sched-now-dot`, appended in the grid section of
`tokens.css`. No time chip in the gutter (keep it minimal; the line + the
highlighted `Today` header column carry the meaning).

## 4. Tests

`nowMinutesOfDay` is covered in `gridtime.test.ts` (G-A). The render
condition is one equality on values already unit-tested via
`windowStartMs`/`todayDayMs` (`datetime.test.ts`); the JSX itself is covered
by the G-D browser smoke (line sits at the wall-clock hour, absent when
paging to a later window). No new test file.

## Acceptance

- With the draft's timezone set to the user's own, the line sits at the
  current wall-clock time on today's column and moves after ≥1 tick.
- Paging → to a future window hides the line; paging back shows it.
- The line never intercepts pointer events (drag across it works).
